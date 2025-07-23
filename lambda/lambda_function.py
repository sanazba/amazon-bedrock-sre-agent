import json
import logging
import os
import boto3
import requests
from datetime import datetime
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

def lambda_handler(event, context):
    """
    Main Lambda handler for Bedrock Agent Kubernetes tools
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Extract information from Bedrock Agent event
        action_group = event.get('actionGroup', '')
        api_path = event.get('apiPath', '')
        http_method = event.get('httpMethod', '')
        input_text = event.get('inputText', '')
        
        logger.info(f"Action Group: {action_group}")
        logger.info(f"API Path: {api_path}")
        logger.info(f"HTTP Method: {http_method}")
        logger.info(f"Input Text: {input_text}")
        
        # Extract parameters from request body
        parameters = {}
        request_body = event.get('requestBody', {})
        if request_body and 'content' in request_body:
            content = request_body['content']
            if 'application/json' in content:
                properties = content['application/json'].get('properties', [])
                for prop in properties:
                    if 'name' in prop and 'value' in prop:
                        parameters[prop['name']] = prop['value']
        
        logger.info(f"Extracted Parameters: {parameters}")
        
        # Define clusters to check
        clusters = [os.environ.get('CLUSTER_NAME', 'test-cluster-production')]
        logger.info(f"Clusters to check: {clusters}")
        
        # Route to appropriate function based on API path
        if api_path == '/get-pods':
            namespace = parameters.get('namespace', '')
            logger.info(f"Calling get_pods_from_cluster with namespace: '{namespace}'")
            result = get_pods_from_cluster(clusters, namespace)
        elif api_path == '/analyze-namespace':
            namespace = parameters.get('namespace', '')
            logger.info(f"Calling get_cluster_data_with_real_kubernetes_api for path: {api_path}")
            result = get_cluster_data_with_real_kubernetes_api(clusters, namespace)
        elif api_path == '/get-cluster-health':
            logger.info(f"Calling get_cluster_data_with_real_kubernetes_api for path: {api_path}")
            result = get_cluster_data_with_real_kubernetes_api(clusters)
        elif api_path == '/create-pod':
            name = parameters.get('name', 'test-pod')
            image = parameters.get('image', 'nginx')
            namespace = parameters.get('namespace', 'default')
            result = create_pod_in_cluster(clusters, name, image, namespace)
        else:
            result = {
                'error': f'Unknown API path: {api_path}',
                'available_paths': ['/get-pods', '/analyze-namespace', '/get-cluster-health', '/create-pod']
            }
        
        logger.info(f"Function result keys: {list(result.keys())}")
        logger.info(f"Responding with API Path: {api_path}")
        
        # Return response in Bedrock Agent format
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': action_group,
                'apiPath': api_path,
                'httpMethod': http_method,
                'httpStatusCode': 200,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(result)
                    }
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': action_group,
                'apiPath': api_path,
                'httpMethod': http_method,
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({
                            'error': str(e),
                            'timestamp': datetime.utcnow().isoformat()
                        })
                    }
                }
            }
        }

def get_kubernetes_config(cluster_name):
    """Get Kubernetes cluster configuration"""
    try:
        # Get cluster info from EKS
        eks_client = boto3.client('eks')
        cluster_info = eks_client.describe_cluster(name=cluster_name)
        
        cluster_endpoint = cluster_info['cluster']['endpoint']
        cluster_ca = cluster_info['cluster']['certificateAuthority']['data']
        
        # Get token from environment variable
        token = os.environ.get('KUBERNETES_TOKEN')
        if not token:
            logger.error("No KUBERNETES_TOKEN environment variable found")
            return None, None, None
        
        logger.info(f"Using service account token (length: {len(token)})")
        
        return cluster_endpoint, cluster_ca, token
        
    except Exception as e:
        logger.error(f"Error getting Kubernetes config: {str(e)}")
        return None, None, None

def get_pods_from_cluster(clusters, namespace=""):
    """Get pods from Kubernetes cluster using direct API calls"""
    try:
        results = []
        
        for cluster_name in clusters:
            cluster_endpoint, cluster_ca, token = get_kubernetes_config(cluster_name)
            if not cluster_endpoint:
                continue
            
            # Build API URL
            if namespace:
                api_url = f"{cluster_endpoint}/api/v1/namespaces/{namespace}/pods"
            else:
                api_url = f"{cluster_endpoint}/api/v1/pods"
            
            logger.info(f"Getting pods from: {api_url}")
            
            # Make request to Kubernetes API
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }
            
            response = requests.get(api_url, headers=headers, verify=False, timeout=30)
            
            if response.status_code == 200:
                pods_data = response.json()
                pods = []
                
                for pod in pods_data.get('items', []):
                    pod_info = {
                        'name': pod['metadata']['name'],
                        'namespace': pod['metadata']['namespace'],
                        'status': pod['status']['phase'],
                        'node': pod['spec'].get('nodeName', 'Unknown'),
                        'created': pod['metadata']['creationTimestamp']
                    }
                    pods.append(pod_info)
                
                results.extend(pods)
            else:
                logger.error(f"Failed to get pods: {response.status_code} - {response.text}")
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'clusters_checked': clusters,
            'data_source': 'kubernetes_api',
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error getting pods: {str(e)}")
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
            'clusters_checked': clusters,
            'data_source': 'kubernetes_api'
        }

def get_cluster_data_with_real_kubernetes_api(clusters, namespace=""):
    """Get comprehensive cluster data including namespaces"""
    try:
        cluster_data = []
        
        for cluster_name in clusters:
            logger.info(f"Processing cluster: {cluster_name}")
            
            cluster_endpoint, cluster_ca, token = get_kubernetes_config(cluster_name)
            if not cluster_endpoint:
                continue
            
            # Get namespaces
            namespaces_url = f"{cluster_endpoint}/api/v1/namespaces"
            logger.info(f"Calling Kubernetes API: {namespaces_url}")
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }
            
            response = requests.get(namespaces_url, headers=headers, verify=False, timeout=30)
            logger.info(f"API response status: {response.status_code}")
            
            if response.status_code == 200:
                namespaces_data = response.json()
                namespaces = []
                
                for ns in namespaces_data.get('items', []):
                    ns_info = {
                        'name': ns['metadata']['name'],
                        'status': ns['status']['phase'],
                        'created': ns['metadata']['creationTimestamp'],
                        'labels': ns['metadata'].get('labels', {})
                    }
                    namespaces.append(ns_info)
                
                cluster_info = {
                    'cluster_name': cluster_name,
                    'endpoint': cluster_endpoint,
                    'namespaces': namespaces,
                    'namespace_count': len(namespaces)
                }
                cluster_data.append(cluster_info)
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'clusters_checked': clusters,
            'data_source': 'kubernetes_api',
            'clusters': cluster_data,
            'summary': f"Found {len(cluster_data)} clusters with namespace information"
        }
        
    except Exception as e:
        logger.error(f"Error getting cluster data: {str(e)}")
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
            'clusters_checked': clusters,
            'data_source': 'kubernetes_api',
            'clusters': [],
            'summary': f"Error retrieving cluster data: {str(e)}"
        }

def create_pod_in_cluster(clusters, pod_name, image, namespace="default"):
    """Create a pod in the Kubernetes cluster"""
    try:
        results = []
        
        for cluster_name in clusters:
            cluster_endpoint, cluster_ca, token = get_kubernetes_config(cluster_name)
            if not cluster_endpoint:
                continue
            
            # Build pod manifest
            pod_manifest = {
                'apiVersion': 'v1',
                'kind': 'Pod',
                'metadata': {
                    'name': pod_name,
                    'namespace': namespace,
                    'labels': {
                        'created-by': 'bedrock-agent',
                        'app': pod_name
                    }
                },
                'spec': {
                    'containers': [
                        {
                            'name': pod_name,
                            'image': image,
                            'ports': [
                                {
                                    'containerPort': 80
                                }
                            ]
                        }
                    ],
                    'restartPolicy': 'Always'
                }
            }
            
            # Create pod via API
            api_url = f"{cluster_endpoint}/api/v1/namespaces/{namespace}/pods"
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            response = requests.post(
                api_url, 
                headers=headers, 
                json=pod_manifest, 
                verify=False, 
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = {
                    'cluster': cluster_name,
                    'pod_name': pod_name,
                    'namespace': namespace,
                    'image': image,
                    'status': 'created',
                    'message': f"Pod {pod_name} created successfully in namespace {namespace}"
                }
            else:
                result = {
                    'cluster': cluster_name,
                    'pod_name': pod_name,
                    'namespace': namespace,
                    'image': image,
                    'status': 'failed',
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
            
            results.append(result)
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'clusters_checked': clusters,
            'data_source': 'kubernetes_api',
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error creating pod: {str(e)}")
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
            'clusters_checked': clusters,
            'data_source': 'kubernetes_api'
        }