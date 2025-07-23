import json
import boto3
import base64
import os
import logging
from datetime import datetime

# Set up logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

def lambda_handler(event, context):
    """Automatically refresh Kubernetes service account tokens"""
    try:
        logger.info("Starting automatic token refresh...")
        
        target_function = os.environ.get('TARGET_LAMBDA_FUNCTION')
        cluster_name = os.environ.get('CLUSTER_NAME')
        
        logger.info(f"Target function: {target_function}")
        logger.info(f"Cluster name: {cluster_name}")
        
        # Get fresh token
        token = get_kubernetes_token(cluster_name)
        if not token:
            raise Exception("Failed to get Kubernetes token")
        
        # Update Lambda environment
        success = update_lambda_environment(target_function, token, cluster_name)
        
        if success:
            logger.info("✅ Token refresh completed successfully")
            return {'statusCode': 200, 'body': json.dumps({'message': 'Token updated successfully'})}
        else:
            raise Exception("Failed to update Lambda environment")
        
    except Exception as e:
        logger.error(f"❌ Error in token refresh: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

def get_kubernetes_token(cluster_name):
    """Get service account token using AWS CLI approach"""
    try:
        import subprocess
        
        # Configure kubectl context first
        subprocess.run([
            'aws', 'eks', 'update-kubeconfig', 
            '--region', 'eu-central-1',
            '--name', cluster_name
        ], check=True, capture_output=True)
        
        # Get token from secret
        result = subprocess.run([
            'kubectl', 'get', 'secret', 'bedrock-agent-token',
            '-n', 'kube-system', 
            '-o', 'jsonpath={.data.token}'
        ], capture_output=True, text=True, check=True)
        
        token_b64 = result.stdout.strip()
        token = base64.b64decode(token_b64).decode('utf-8')
        
        logger.info(f"Retrieved token (length: {len(token)} characters)")
        return token
        
    except Exception as e:
        logger.error(f"Error getting Kubernetes token: {str(e)}")
        return None

def update_lambda_environment(function_name, token, cluster_name):
    """Update target Lambda function environment with new token"""
    try:
        lambda_client = boto3.client('lambda')
        
        env_vars = {
            'LOG_LEVEL': 'INFO',
            'KUBERNETES_TOKEN': token,
            'CLUSTER_NAME': cluster_name,
            'ENVIRONMENT': 'production',
            'PROJECT': 'bedrock-sre-agent',
            'TOKEN_UPDATED': datetime.utcnow().isoformat()
        }
        
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Environment={'Variables': env_vars}
        )
        
        logger.info(f"Updated Lambda {function_name} with new token")
        return True
        
    except Exception as e:
        logger.error(f"Error updating Lambda environment: {str(e)}")
        return False
