terraform {
  backend "s3" {
    bucket       = "incident-recovery-tfstate-275956876816-us-east-1"
    key          = "bootstrap/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true


  }
}
