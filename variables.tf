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

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "k8s-sre-tools"
}

variable "lambda_runtime" {
  description = "Lambda runtime version"
  type        = string
  default     = "python3.11"
}

variable "agent_name" {
  description = "Name of the Bedrock Agent"
  type        = string
  default     = "SRE-Kubernetes-Assistant"
}

variable "agent_description" {
  description = "Description of the Bedrock Agent"
  type        = string
  default     = "AI assistant for Kubernetes cluster management and SRE operations"
}

variable "foundation_model" {
  description = "Foundation model for the Bedrock Agent"
  type        = string
  default     = "anthropic.claude-3-haiku-20240307-v1:0"
}

variable "agent_instruction" {
  description = "Instructions for the Bedrock Agent"
  type        = string
  default     = "You are a Site Reliability Engineering (SRE) assistant specialized in Kubernetes cluster management. You can help users manage Kubernetes clusters, check pod status, analyze namespaces, create deployments, and perform various cluster operations through natural language commands. Always provide clear, helpful responses about the cluster state and operations."
}

variable "action_group_name" {
  description = "Name of the Bedrock Agent action group"
  type        = string
  default     = "kubernetes-tools"
}