# 🚀 Bedrock SRE Agent - Kubernetes Management

A production-ready AWS Bedrock Agent that manages real Kubernetes clusters through natural language commands.

## ✨ What This Does

Talk to your Kubernetes cluster in plain English through AWS Bedrock Console:
- **"list all pods"** → Shows all pods across namespaces
- **"show cluster health"** → Displays cluster status and namespaces  
- **"create nginx pod"** → Deploys an nginx pod
- **"analyze namespaces"** → Get detailed namespace information
- **"check nodes"** → Monitor node health and status

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  AWS Console    │───▶│  Bedrock Agent   │───▶│  Lambda + EKS   │
│ (Natural Lang)  │    │  (AI Interface)  │    │ (Real K8s API)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

**Components:**
- **AWS Bedrock Agent** - Natural language interface
- **AWS Lambda** - Kubernetes API integration  
- **Amazon EKS** - Managed Kubernetes cluster
- **Service Account** - Secure authentication
- **Terraform** - Infrastructure as Code

## 📁 Project Structure

```
bedrock-sre-agent/
├── .gitignore              # Prevents large files from being committed
├── main.tf                 # Main Terraform infrastructure
├── variables.tf            # Terraform variables
├── outputs.tf              # Terraform outputs
├── lambda/
│   └── lambda_function.py  # Kubernetes API integration
├── token_manager.py        # Python script to set authentication token
└── README.md              # This file
```

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Install required tools
brew install terraform kubectl awscli python3  # macOS
# or
apt-get install terraform kubectl awscli python3  # Ubuntu

# Configure AWS credentials
aws configure
```

### 2. Deploy Infrastructure

```bash
# Initialize and deploy
terraform init
terraform plan
terraform apply
```

### 3. Set Authentication Token

```bash
# Simple Python script to set the token
python3 token_manager.py
```

### 4. Test Your Agent

Go to **AWS Console → Bedrock → Agents → "SRE-Kubernetes-Assistant"**

Try these commands:
- `list all pods`
- `show cluster health`
- `check nodes`
- `analyze namespace kube-system`
- `describe pod <pod-name>`

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `LOG_LEVEL` | Lambda logging level | `INFO` |
| `KUBERNETES_TOKEN` | Service account token | `eyJhbG...` |
| `CLUSTER_NAME` | EKS cluster name | `test-cluster-production` |

### Terraform Variables

Edit `variables.tf`:

```hcl
variable "aws_region" {
  default = "eu-central-1"
}

variable "project_name" {
  default = "bedrock-sre-agent"
}

variable "environment" {
  default = "production"
}
```

## 🛠️ Management Commands

### Infrastructure

```bash
# Deploy everything
terraform apply

# Check status
terraform output

# Destroy everything
terraform destroy
```

### Token Management

```bash
# Check current token status
aws lambda get-function-configuration \
  --function-name k8s-sre-tools \
  --query 'Environment.Variables.KUBERNETES_TOKEN'

# Update token when needed
python3 token_manager.py
```

### Debugging

```bash
# Check Lambda logs
aws logs tail /aws/lambda/k8s-sre-tools --follow

# Check EKS cluster
aws eks describe-cluster --name test-cluster-production

# Test kubectl access
kubectl get pods --all-namespaces
```

## 🏢 Production Deployment

### Security Considerations

1. **Service Account Permissions**: Uses cluster-admin (consider limiting in production)
2. **Network Security**: Lambda in private subnet recommended
3. **Token Rotation**: Consider automatic token rotation
4. **Audit Logging**: Enable EKS audit logs

### Scaling

- **Multi-cluster**: Modify Lambda to support multiple EKS clusters
- **RBAC**: Implement fine-grained permissions per user
- **Monitoring**: Add CloudWatch dashboards and alerts

### CI/CD Integration

```yaml
# GitHub Actions example
name: Deploy SRE Agent
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
      - name: Deploy
        run: |
          terraform init
          terraform apply -auto-approve
          python3 token_manager.py
```

## 🔍 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Access denied" | Check Lambda permissions for Bedrock |
| "Token not configured" | Run `python3 token_manager.py` |
| "Cluster not found" | Verify EKS cluster exists and region is correct |
| Agent not responding | Check Bedrock Agent is deployed and alias is active |

### Getting Help

1. **Check logs**: `aws logs tail /aws/lambda/k8s-sre-tools --follow`
2. **Verify token**: Test kubectl with the same token
3. **Test Lambda**: Use AWS Console to test the function directly

## 📊 Available Commands

### Cluster Management
- **"show cluster health"** - Overall cluster status
- **"check nodes"** - Node health and capacity
- **"list all pods"** - All pods across namespaces

### Pod Operations
- **"describe pod <name>"** - Detailed pod information
- **"get pods in <namespace>"** - Namespace-specific pods

### Namespace Analysis
- **"analyze namespace <name>"** - Detailed namespace info
- **"list all namespaces"** - All available namespaces

## 🚀 What You Built

This is a **production-ready SRE automation platform** that demonstrates:

- ✅ **Infrastructure as Code** with Terraform
- ✅ **AI-powered operations** with Bedrock Agents
- ✅ **Real Kubernetes management** via APIs
- ✅ **Secure authentication** with service accounts
- ✅ **Serverless architecture** with Lambda
- ✅ **Enterprise-grade security** and monitoring

Perfect for showing stakeholders the future of **AI-driven infrastructure management**!

## 📝 License

MIT License - Feel free to use this in your organization.

---

**Built for real-world SRE teams who want to manage Kubernetes clusters through natural language.** 🎯

**Components:**
- **AWS Bedrock Agent** - Natural language interface
- **AWS Lambda** - Kubernetes API integration  
- **Amazon EKS** - Managed Kubernetes cluster
- **Service Account** - Secure authentication
- **Terraform** - Infrastructure as Code

## 📁 Project Structure

```
bedrock-sre-agent/
├── main.tf              # Main Terraform configuration
├── variables.tf         # Terraform variables
├── outputs.tf          # Terraform outputs
├── lambda/
│   └── lambda_function.py  # Kubernetes API integration
├── token_manager.py     # Token updater (Python)
└── README.md           # This file
```
