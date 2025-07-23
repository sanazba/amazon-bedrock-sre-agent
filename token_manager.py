#!/usr/bin/env python3
"""
Simple token manager for Bedrock SRE Agent
Usage: python3 token_manager.py
"""

import subprocess
import boto3
import json
import base64

def get_kubernetes_token():
    """Get service account token from Kubernetes"""
    try:
        cmd = ["kubectl", "get", "secret", "bedrock-agent-token", 
               "-n", "kube-system", "-o", "jsonpath={.data.token}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        token_b64 = result.stdout.strip()
        token = base64.b64decode(token_b64).decode('utf-8')
        return token
    except subprocess.CalledProcessError as e:
        print(f"❌ Error getting token: {e}")
        return None

def update_lambda_token(token):
    """Update Lambda environment with new token"""
    try:
        lambda_client = boto3.client('lambda', region_name='eu-central-1')
        
        env_vars = {
            "LOG_LEVEL": "INFO",
            "KUBERNETES_TOKEN": token,
            "CLUSTER_NAME": "test-cluster-production",
            "ENVIRONMENT": "production",
            "PROJECT": "bedrock-sre-agent"
        }
        
        response = lambda_client.update_function_configuration(
            FunctionName='k8s-sre-tools',
            Environment={'Variables': env_vars}
        )
        
        print("✅ Lambda token updated successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error updating Lambda: {e}")
        return False

def main():
    print("🔑 Updating Bedrock SRE Agent token...")
    
    # Get token from Kubernetes
    token = get_kubernetes_token()
    if not token:
        return
    
    print(f"Token length: {len(token)} characters")
    
    # Update Lambda
    if update_lambda_token(token):
        print("🎯 Your Bedrock Agent is ready!")
        print("Test commands:")
        print("  • 'list all pods'")
        print("  • 'show cluster health'")
        print("  • 'check nodes'")
        print("  • 'analyze namespace kube-system'")
    else:
        print("❌ Failed to update token")

if __name__ == "__main__":
    main()
