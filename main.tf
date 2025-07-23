# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local values
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# =============================================================================
# EKS CLUSTER SETUP
# =============================================================================

# EKS Cluster IAM Role
resource "aws_iam_role" "eks_cluster_role" {
  name = "${var.project_name}-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster_role.name
}

# EKS Node Group IAM Role
resource "aws_iam_role" "eks_nodegroup_role" {
  name = "${var.project_name}-eks-nodegroup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "eks_worker_node_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.eks_nodegroup_role.name
}

resource "aws_iam_role_policy_attachment" "eks_cni_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.eks_nodegroup_role.name
}

resource "aws_iam_role_policy_attachment" "eks_container_registry_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.eks_nodegroup_role.name
}

# Use default VPC if no specific VPC is configured
data "aws_vpc" "selected" {
  default = true
}

# Get subnets from the VPC
data "aws_subnets" "selected" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.selected.id]
  }
}

# Use subnet IDs from data source
locals {
  eks_subnet_ids = data.aws_subnets.selected.ids
}

# EKS Cluster
resource "aws_eks_cluster" "test_cluster" {
  name     = "test-cluster-${var.environment}"
  role_arn = aws_iam_role.eks_cluster_role.arn
  version  = "1.33"

  vpc_config {
    subnet_ids              = local.eks_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = ["0.0.0.0/0"]
  }

  enabled_cluster_log_types = ["api", "audit"]

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy
  ]

  tags = merge(local.common_tags, {
    Name = "test-cluster-${var.environment}"
  })
}

# EKS Node Group
resource "aws_eks_node_group" "test_nodes" {
  cluster_name    = aws_eks_cluster.test_cluster.name
  node_group_name = "test"
  node_role_arn   = aws_iam_role.eks_nodegroup_role.arn
  subnet_ids      = local.eks_subnet_ids

  instance_types = ["t3.medium"]
  ami_type       = "AL2023_x86_64_STANDARD"
  capacity_type  = "ON_DEMAND"
  disk_size      = 20

  scaling_config {
    desired_size = 2
    max_size     = 3
    min_size     = 1
  }

  update_config {
    max_unavailable = 1
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.eks_container_registry_policy
  ]

  tags = merge(local.common_tags, {
    Name = "test-nodegroup"
    NodeGroup = "test"
  })
  
  lifecycle {
    ignore_changes = [
      scaling_config[0].desired_size
    ]
  }
}

# Create service account for Bedrock Agent
resource "kubernetes_service_account" "bedrock_agent" {
  metadata {
    name      = "bedrock-agent"
    namespace = "kube-system"
  }

  depends_on = [aws_eks_node_group.test_nodes]
}

# Create cluster role binding for the service account
resource "kubernetes_cluster_role_binding" "bedrock_agent" {
  metadata {
    name = "bedrock-agent-binding"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = "cluster-admin"
  }

  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.bedrock_agent.metadata[0].name
    namespace = kubernetes_service_account.bedrock_agent.metadata[0].namespace
  }

  depends_on = [kubernetes_service_account.bedrock_agent]
}

# Create secret for the service account token
resource "kubernetes_secret" "bedrock_agent_token" {
  metadata {
    name      = "bedrock-agent-token"
    namespace = "kube-system"
    annotations = {
      "kubernetes.io/service-account.name" = kubernetes_service_account.bedrock_agent.metadata[0].name
    }
  }

  type = "kubernetes.io/service-account-token"

  depends_on = [kubernetes_service_account.bedrock_agent]
}

# Data sources to read the created resources
data "kubernetes_service_account" "bedrock_agent" {
  metadata {
    name      = kubernetes_service_account.bedrock_agent.metadata[0].name
    namespace = kubernetes_service_account.bedrock_agent.metadata[0].namespace
  }
  depends_on = [kubernetes_service_account.bedrock_agent]
}

data "kubernetes_secret" "bedrock_agent_token" {
  metadata {
    name      = kubernetes_secret.bedrock_agent_token.metadata[0].name
    namespace = kubernetes_secret.bedrock_agent_token.metadata[0].namespace
  }
  depends_on = [kubernetes_secret.bedrock_agent_token]
}

# =============================================================================
# BEDROCK AGENT SETUP
# =============================================================================

# IAM Role for Bedrock Agent
resource "aws_iam_role" "bedrock_agent_role" {
  name = "${var.project_name}-bedrock-agent-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "arn:aws:bedrock:${local.region}:${local.account_id}:agent/*"
          }
        }
      }
    ]
  })

  tags = local.common_tags
}

# Custom policy for Bedrock Agent with Lambda permissions
resource "aws_iam_role_policy" "bedrock_agent_policy" {
  name = "${var.project_name}-bedrock-agent-policy"
  role = aws_iam_role.bedrock_agent_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${local.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
          "arn:aws:bedrock:${local.region}::foundation-model/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.k8s_tools.arn,
          "${aws_lambda_function.k8s_tools.arn}:*"
        ]
      }
    ]
  })
}

# IAM Role for Lambda Function
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-lambda-execution-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# EKS permissions for Lambda
resource "aws_iam_role_policy" "lambda_eks_policy" {
  name = "${var.project_name}-lambda-eks-policy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:ListClusters", 
          "eks:DescribeNodegroup",
          "eks:ListNodegroups",
          "eks:AccessKubernetesApi"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sts:GetCallerIdentity"
        ]
        Resource = "*"
      }
    ]
  })
}

# Create ZIP file from Lambda source code  
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda.zip"
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = 14

  tags = local.common_tags
}

# Lambda Function
resource "aws_lambda_function" "k8s_tools" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = var.lambda_function_name
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = var.lambda_runtime
  timeout         = 60
  memory_size     = 512
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  description = "Real Kubernetes API Lambda function for Bedrock Agent"

  environment {
    variables = {
      ENVIRONMENT    = var.environment
      PROJECT        = var.project_name
      LOG_LEVEL      = "INFO"
      CLUSTER_NAME   = aws_eks_cluster.test_cluster.name
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.lambda_logs,
  ]

  tags = local.common_tags
}

# Permission for Bedrock to invoke Lambda
resource "aws_lambda_permission" "allow_bedrock" {
  statement_id  = "AllowExecutionFromBedrock"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.k8s_tools.function_name
  principal     = "bedrock.amazonaws.com"
  source_arn    = "arn:aws:bedrock:${local.region}:${local.account_id}:agent/*"
}

# =============================================================================
# AUTOMATED TOKEN REFRESH SYSTEM
# =============================================================================

# Create ZIP file for token refresher Lambda
data "archive_file" "token_refresher_zip" {
  type        = "zip"
  source_dir  = "${path.module}/token_refresher"
  output_path = "${path.module}/token_refresher.zip"
}

# IAM role for token refresher Lambda
resource "aws_iam_role" "token_refresher_role" {
  name = "${var.project_name}-token-refresher-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# Basic Lambda execution policy for token refresher
resource "aws_iam_role_policy_attachment" "token_refresher_basic_execution" {
  role       = aws_iam_role.token_refresher_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Custom policy for token refresher
resource "aws_iam_role_policy" "token_refresher_policy" {
  name = "${var.project_name}-token-refresher-policy"
  role = aws_iam_role.token_refresher_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "lambda:UpdateFunctionConfiguration",
          "lambda:GetFunctionConfiguration"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sts:GetCallerIdentity"
        ]
        Resource = "*"
      }
    ]
  })
}

# CloudWatch Log Group for token refresher
resource "aws_cloudwatch_log_group" "token_refresher_logs" {
  name              = "/aws/lambda/${var.project_name}-token-refresher"
  retention_in_days = 14
  tags              = local.common_tags
}

# Token refresher Lambda function
resource "aws_lambda_function" "token_refresher" {
  filename         = data.archive_file.token_refresher_zip.output_path
  function_name    = "${var.project_name}-token-refresher"
  role            = aws_iam_role.token_refresher_role.arn
  handler         = "token_refresher.lambda_handler"
  runtime         = "python3.11"
  timeout         = 60
  memory_size     = 256
  source_code_hash = data.archive_file.token_refresher_zip.output_base64sha256

  description = "Automatically refresh Kubernetes service account tokens"

  environment {
    variables = {
      TARGET_LAMBDA_FUNCTION = aws_lambda_function.k8s_tools.function_name
      CLUSTER_NAME          = aws_eks_cluster.test_cluster.name
      LOG_LEVEL            = "INFO"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.token_refresher_basic_execution,
    aws_cloudwatch_log_group.token_refresher_logs,
    kubernetes_secret.bedrock_agent_token
  ]

  tags = local.common_tags
}

# EventBridge rule to trigger token refresh every hour
resource "aws_cloudwatch_event_rule" "token_refresh_schedule" {
  name                = "${var.project_name}-token-refresh"
  description         = "Trigger token refresh every hour"
  schedule_expression = "rate(1 hour)"

  tags = local.common_tags
}

# EventBridge target
resource "aws_cloudwatch_event_target" "token_refresh_target" {
  rule      = aws_cloudwatch_event_rule.token_refresh_schedule.name
  target_id = "TokenRefreshTarget"
  arn       = aws_lambda_function.token_refresher.arn
}

# Permission for EventBridge to invoke token refresher Lambda
resource "aws_lambda_permission" "allow_eventbridge_token_refresh" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.token_refresher.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.token_refresh_schedule.arn
}

# Bedrock Agent
resource "aws_bedrockagent_agent" "sre_agent" {
  agent_name                  = var.agent_name
  agent_resource_role_arn     = aws_iam_role.bedrock_agent_role.arn
  description                 = var.agent_description
  foundation_model            = var.foundation_model
  instruction                 = var.agent_instruction
  idle_session_ttl_in_seconds = 1800

  tags = local.common_tags
}

# Agent Action Group
resource "aws_bedrockagent_agent_action_group" "k8s_tools" {
  action_group_name          = var.action_group_name
  agent_id                   = aws_bedrockagent_agent.sre_agent.agent_id
  agent_version             = "DRAFT"
  description               = "Kubernetes tools for real cluster analysis and troubleshooting"
  
  action_group_executor {
    lambda = aws_lambda_function.k8s_tools.arn
  }

  api_schema {
    payload = jsonencode({
      openapi = "3.0.0"
      info = {
        title   = "Real Kubernetes SRE Tools API"
        version = "1.0.0"
        description = "API for real Kubernetes cluster management"
      }
      paths = {
        "/get-cluster-health" = {
          post = {
            summary     = "Get cluster health"
            description = "Get overall cluster health status"
            operationId = "getClusterHealth"
            responses = {
              "200" = {
                description = "Successful response"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                    }
                  }
                }
              }
            }
          }
        }
        "/get-pods" = {
          post = {
            summary     = "Get pod status"
            description = "Get status of pods in the cluster"
            operationId = "getPods"
            requestBody = {
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      namespace = {
                        type = "string"
                        description = "Namespace to check"
                      }
                    }
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "Successful response"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                    }
                  }
                }
              }
            }
          }
        }
        "/describe-pod" = {
          post = {
            summary     = "Describe pod"
            description = "Get detailed pod information"
            operationId = "describePod"
            requestBody = {
              required = true
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      pod_name = {
                        type = "string"
                        description = "Name of the pod"
                      }
                      namespace = {
                        type = "string"
                        description = "Namespace of the pod"
                      }
                    }
                    required = ["pod_name"]
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "Successful response"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                    }
                  }
                }
              }
            }
          }
        }
        "/check-nodes" = {
          post = {
            summary     = "Check nodes"
            description = "Check node health and status"
            operationId = "checkNodes"
            responses = {
              "200" = {
                description = "Successful response"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                    }
                  }
                }
              }
            }
          }
        }
        "/analyze-namespace" = {
          post = {
            summary     = "Describe namespace"
            description = "Analyze a specific namespace"
            operationId = "analyzeNamespace"
            requestBody = {
              required = true
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      namespace = {
                        type = "string"
                        description = "Namespace to analyze"
                      }
                    }
                    required = ["namespace"]
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "Successful response"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                    }
                  }
                }
              }
            }
          }
        }
      }
    })
  }

  depends_on = [
    aws_lambda_permission.allow_bedrock
  ]
}

# Agent Alias
resource "aws_bedrockagent_agent_alias" "sre_agent_alias" {
  agent_alias_name = "production"
  agent_id         = aws_bedrockagent_agent.sre_agent.agent_id
  description      = "Production alias for SRE Agent"

  tags = local.common_tags
}