resource "aws_db_subnet_group" "platform" {
  name = "${local.resource_prefix}-database"

  subnet_ids = [
    aws_subnet.public_a.id,
    aws_subnet.public_b.id,
  ]

  tags = {
    Name = "${local.resource_prefix}-database"
  }
}

resource "aws_db_instance" "platform" {
  identifier = "${local.resource_prefix}-postgres"

  engine         = "postgres"
  engine_version = "16"

  instance_class        = "db.t4g.micro"
  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "ecommerce"
  username = "incidentadmin"

  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.platform.name
  vpc_security_group_ids = [aws_security_group.database.id]

  publicly_accessible = false
  multi_az            = false

  backup_retention_period    = 1
  auto_minor_version_upgrade = true

  deletion_protection = false
  skip_final_snapshot = true

  apply_immediately = true

  tags = {
    Name = "${local.resource_prefix}-postgres"
  }
}
