# Bootstrap S3 backend for Terraform state
terraform {
  backend "s3" {
    bucket       = "tai-lam-terraform-state-hk"
    key          = "terraform.tfstate"
    region       = "ap-east-1"
    encrypt      = true
    use_lockfile = true
  }
}