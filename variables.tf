variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "test-cluster-production"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "bedrock-sre-agent"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}