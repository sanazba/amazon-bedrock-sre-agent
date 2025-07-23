import json
import logging
import os
import boto3
import urllib3
import ssl
from datetime import datetime

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
        elif api_path == '/check-nodes':
            result = check_nodes(clusters)
        elif api_path == '/describe-pod':
            pod_name = parameters.get('pod_name', '')
            namespace = parameters.get('namespace', 'default')
            result = describe_pod(clusters, pod_name, namespace)
        else:
            result = {
                'error': f'Unknown API path: {api_path}',
                'available_paths': ['/get-pods', '/analyze-namespace', '/get-cluster-health', '/check-nodes', '/describe-pod']
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

def make_k8s_request(url, token, method='GET', data=None):
    """Make HTTP request to Kubernetes API using urllib3"""
    try:
        http = urllib3.PoolManager(cert_reqs='CERT_NONE', assert_hostname=False)
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        if method == 'GET':
            response = http.request('GET', url, headers=headers, timeout=30)
        elif method == 'POST':
            response = http.request('POST', url, headers=headers, body=json.dumps(data), timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        if response.status == 200 or response.status == 201:
            return json.loads(response.data.decode('utf-8'))
        else:
            logger.error(f"K8s API error: {response.status} - {response.data.decode('utf-8')}")
            return None
            
    except Exception as e:
        logger.error(f"Error making K8s request: {str(e)}")
        return None

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
            
            pods_data = make_k8s_request(api_url, token)
            if pods_data:
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
            
            namespaces_data = make_k8s_request(namespaces_url, token)
            if namespaces_data:
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

def check_nodes(clusters):
    """Check node health and status"""
    try:
        results = []
        
        for cluster_name in clusters:
            cluster_endpoint, cluster_ca, token = get_kubernetes_config(cluster_name)
            if not cluster_endpoint:
                continue
            
            nodes_url = f"{cluster_endpoint}/api/v1/nodes"
            logger.info(f"Getting nodes from: {nodes_url}")
            
            nodes_data = make_k8s_request(nodes_url, token)
            if nodes_data:
                nodes = []
                for node in nodes_data.get('items', []):
                    node_info = {
                        'name': node['metadata']['name'],
                        'status': 'Ready' if any(condition['type'] == 'Ready' and condition['status'] == 'True' 
                                               for condition in node['status']['conditions']) else 'NotReady',
                        'version': node['status']['nodeInfo']['kubeletVersion'],
                        'instance_type': node['metadata']['labels'].get('node.kubernetes.io/instance-type', 'Unknown'),
                        'created': node['metadata']['creationTimestamp']
                    }
                    nodes.append(node_info)
                results.extend(nodes)
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'clusters_checked': clusters,
            'data_source': 'kubernetes_api',
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error checking nodes: {str(e)}")
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
            'clusters_checked': clusters,
            'data_source': 'kubernetes_api'
        }

def describe_pod(clusters, pod_name, namespace="default"):
    """Get detailed pod information"""
    try:
        results = []
        
        for cluster_name in clusters:
            cluster_endpoint, cluster_ca, token = get_kubernetes_config(cluster_name)
            if not cluster_endpoint:
                continue
            
            pod_url = f"{cluster_endpoint}/api/v1/namespaces/{namespace}/pods/{pod_name}"
            logger.info(f"Describing pod: {pod_url}")
            
            pod_data = make_k8s_request(pod_url, token)
            if pod_data:
                pod_info = {
                    'name': pod_data['metadata']['name'],
                    'namespace': pod_data['metadata']['namespace'],
                    'status': pod_data['status']['phase'],
                    'node': pod_data['spec'].get('nodeName', 'Unknown'),
                    'created': pod_data['metadata']['creationTimestamp'],
                    'containers': [],
                    'conditions': pod_data['status'].get('conditions', [])
                }
                
                for container in pod_data['spec']['containers']:
                    container_info = {
                        'name': container['name'],
                        'image': container['image'],
                        'ports': container.get('ports', [])
                    }
                    pod_info['containers'].append(container_info)
                
                results.append(pod_info)
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'clusters_checked': clusters,
            'data_source': 'kubernetes_api',
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error describing pod: {str(e)}")
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
            'clusters_checked': clusters,
            'data_source': 'kubernetes_api'
        }