import os

from neo4j import GraphDatabase


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


class LineageQueryService:
    def __init__(self):
        if not NEO4J_PASSWORD:
            raise RuntimeError(
                "NEO4J_PASSWORD is not set. "
                "Load the project .env before using lineage queries."
            )

        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
        )

        self.driver.verify_connectivity()

    def close(self):
        self.driver.close()

    def get_downstream(self, namespace, name):
        query = """
        MATCH p =
            (start:Dataset {
                namespace: $namespace,
                name: $name
            })-[:INPUT_TO|OUTPUTS*1..20]->(node)

        WITH node, min(length(p)) AS hops

        RETURN
            labels(node)[0] AS node_type,
            node.namespace AS namespace,
            node.name AS name,
            hops

        ORDER BY
            hops,
            node_type,
            name
        """

        with self.driver.session() as session:
            result = session.run(
                query,
                namespace=namespace,
                name=name,
            )

            return [record.data() for record in result]

    def get_upstream(self, namespace, name):
        query = """
        MATCH p =
            (start:Dataset {
                namespace: $namespace,
                name: $name
            })<-[:INPUT_TO|OUTPUTS*1..20]-(node)

        WITH node, min(length(p)) AS hops

        RETURN
            labels(node)[0] AS node_type,
            node.namespace AS namespace,
            node.name AS name,
            hops

        ORDER BY
            hops,
            node_type,
            name
        """

        with self.driver.session() as session:
            result = session.run(
                query,
                namespace=namespace,
                name=name,
            )

            return [record.data() for record in result]

    def get_dependency_path(
        self,
        source_namespace,
        source_name,
        target_namespace,
        target_name,
    ):
        query = """
        MATCH
            (source:Dataset {
                namespace: $source_namespace,
                name: $source_name
            }),
            (target:Dataset {
                namespace: $target_namespace,
                name: $target_name
            })

        MATCH p = shortestPath(
            (source)-[:INPUT_TO|OUTPUTS*1..40]->(target)
        )

        RETURN
            [
                node IN nodes(p) |
                {
                    node_type: labels(node)[0],
                    namespace: node.namespace,
                    name: node.name
                }
            ] AS path,
            length(p) AS hops
        """

        with self.driver.session() as session:
            record = session.run(
                query,
                source_namespace=source_namespace,
                source_name=source_name,
                target_namespace=target_namespace,
                target_name=target_name,
            ).single()

            if record is None:
                return None

            return record.data()

    def calculate_blast_radius(self, namespace, name):
        downstream = self.get_downstream(
            namespace=namespace,
            name=name,
        )

        affected_jobs = [
            node
            for node in downstream
            if node["node_type"] == "Job"
        ]

        affected_datasets = [
            node
            for node in downstream
            if node["node_type"] == "Dataset"
        ]

        max_hops = max(
            (node["hops"] for node in downstream),
            default=0,
        )

        return {
            "source": {
                "node_type": "Dataset",
                "namespace": namespace,
                "name": name,
            },
            "affected_jobs": affected_jobs,
            "affected_datasets": affected_datasets,
            "affected_job_count": len(affected_jobs),
            "affected_dataset_count": len(affected_datasets),
            "total_affected_nodes": len(downstream),
            "max_hops": max_hops,
        }


    def get_job_downstream(self, namespace, name):
        """
        Return all downstream nodes reachable from a Job.
        """
        query = """
        MATCH p =
            (start:Job {
                namespace: $namespace,
                name: $name
            })-[:INPUT_TO|OUTPUTS*1..20]->(node)

        WITH node, min(length(p)) AS hops

        RETURN
            labels(node)[0] AS node_type,
            node.namespace AS namespace,
            node.name AS name,
            hops

        ORDER BY
            hops,
            node_type,
            name
        """

        with self.driver.session() as session:
            result = session.run(
                query,
                namespace=namespace,
                name=name,
            )

            return [
                record.data()
                for record in result
            ]

    def get_job_upstream(self, namespace, name):
        """
        Return all upstream nodes that feed a Job.
        """
        query = """
        MATCH p =
            (start:Job {
                namespace: $namespace,
                name: $name
            })<-[:INPUT_TO|OUTPUTS*1..20]-(node)

        WITH node, min(length(p)) AS hops

        RETURN
            labels(node)[0] AS node_type,
            node.namespace AS namespace,
            node.name AS name,
            hops

        ORDER BY
            hops,
            node_type,
            name
        """

        with self.driver.session() as session:
            result = session.run(
                query,
                namespace=namespace,
                name=name,
            )

            return [
                record.data()
                for record in result
            ]

    def calculate_job_blast_radius(
        self,
        namespace,
        name,
    ):
        """
        Calculate downstream impact starting from a Job.
        """
        downstream = self.get_job_downstream(
            namespace=namespace,
            name=name,
        )

        affected_jobs = [
            node
            for node in downstream
            if node["node_type"] == "Job"
        ]

        affected_datasets = [
            node
            for node in downstream
            if node["node_type"] == "Dataset"
        ]

        max_hops = max(
            (
                node["hops"]
                for node in downstream
            ),
            default=0,
        )

        return {
            "source": {
                "node_type": "Job",
                "namespace": namespace,
                "name": name,
            },
            "affected_jobs": affected_jobs,
            "affected_datasets": affected_datasets,
            "affected_job_count": len(
                affected_jobs
            ),
            "affected_dataset_count": len(
                affected_datasets
            ),
            "total_affected_nodes": len(
                downstream
            ),
            "max_hops": max_hops,
        }


if __name__ == "__main__":
    service = LineageQueryService()

    try:
        print("DOWNSTREAM")
        downstream = service.get_downstream(
            namespace="s3://data-platform",
            name="bronze/transactions",
        )

        for node in downstream:
            print(node)

        print("\nUPSTREAM")
        upstream = service.get_upstream(
            namespace="s3://data-platform",
            name="silver/transactions",
        )

        for node in upstream:
            print(node)

        print("\nDEPENDENCY PATH")
        dependency_path = service.get_dependency_path(
            source_namespace="s3://data-platform",
            source_name="bronze/transactions",
            target_namespace="s3://data-platform",
            target_name="silver/transactions",
        )

        print(dependency_path)

        print("\nBLAST RADIUS")
        blast_radius = service.calculate_blast_radius(
            namespace="s3://data-platform",
            name="bronze/transactions",
        )

        print(blast_radius)

    finally:
        service.close()
