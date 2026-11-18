data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "platform" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${local.resource_prefix}-vpc"
  }
}

resource "aws_internet_gateway" "platform" {
  vpc_id = aws_vpc.platform.id

  tags = {
    Name = "${local.resource_prefix}-igw"
  }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.platform.id
  cidr_block              = "10.42.0.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "${local.resource_prefix}-public-a"
  }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.platform.id
  cidr_block              = "10.42.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[1]
  map_public_ip_on_launch = true

  tags = {
    Name = "${local.resource_prefix}-public-b"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.platform.id

  tags = {
    Name = "${local.resource_prefix}-public"
  }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.platform.id
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "alb" {
  name        = "${local.resource_prefix}-alb"
  description = "Public HTTP entry point for incident recovery API"
  vpc_id      = aws_vpc.platform.id
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = var.api_allowed_cidr
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_api" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
}

resource "aws_security_group" "ecs" {
  name        = "${local.resource_prefix}-ecs"
  description = "ECS tasks for incident recovery API and worker"
  vpc_id      = aws_vpc.platform.id
}

resource "aws_vpc_security_group_ingress_rule" "ecs_api_from_alb" {
  security_group_id            = aws_security_group.ecs.id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "ecs_all" {
  security_group_id = aws_security_group.ecs.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "database" {
  name        = "${local.resource_prefix}-database"
  description = "PostgreSQL reachable only from ECS tasks"
  vpc_id      = aws_vpc.platform.id
}

resource "aws_vpc_security_group_ingress_rule" "database_from_ecs" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "database_all" {
  security_group_id = aws_security_group.database.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
