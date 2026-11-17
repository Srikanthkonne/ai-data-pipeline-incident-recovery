terraform {
  backend "s3" {
    bucket       = "incident-recovery-tfstate-275956876816-us-east-1"
    key          = "phase5c/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true

    assume_role = {
      role_arn     = "arn:aws:iam::275956876816:role/IncidentRecoveryProvisioner"
      session_name = "incident-recovery-terraform-backend"
    }
  }
}
