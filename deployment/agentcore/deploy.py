#!/usr/bin/env python3
"""
Amazon Bedrock AgentCore Deployment Script using Starter Toolkit

This script is a Python-based deployment
using the bedrock-agentcore-starter-toolkit.

Usage:
    python deploy.py <websocket-folder> [options]

Examples:
    python deploy.py bedrock-sonic
    python deploy.py strands-sonic --region us-west-2
    python deploy.py langchain-transcribe-polly --agent-name my-langchain-agent
    python deploy.py bedrock-sonic --agent-name my-sonic-agent
"""

import argparse
import json
import os
import sys
import subprocess
import shutil
import time
import traceback
import yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional

import boto3
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
from bedrock_agentcore_starter_toolkit.operations.runtime.launch import launch_bedrock_agentcore


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'  # No Color


class AgentCoreDeployer:
    """Handles deployment of agents to Amazon Bedrock AgentCore Runtime"""

    def __init__(self, websocket_folder: str, args: argparse.Namespace):
        self.websocket_folder = websocket_folder
        self.args = args
        
        # Resolve paths relative to the project root directory
        self.base_dir = Path(__file__).parent.parent.parent
        
        # Search for the websocket folder under samples/
        samples_paths = [
            self.base_dir / "samples" / "bidi-streaming" / websocket_folder,
            self.base_dir / "samples" / "cascading" / websocket_folder,
            self.base_dir / websocket_folder,  # fallback for legacy flat structure
        ]
        
        self.sample_dir = None
        for p in samples_paths:
            if p.exists():
                self.sample_dir = p
                break
        
        if not self.sample_dir:
            self._error(f"Sample folder not found: {websocket_folder}")
            self._error(f"  Searched: {[str(p) for p in samples_paths]}")
            sys.exit(1)
        
        # Validate websocket subfolder exists
        self.websocket_path = self.sample_dir / "websocket"
        if not self.websocket_path.exists():
            # Try 'server' subfolder (livekit samples use this)
            self.websocket_path = self.sample_dir / "server"
        if not self.websocket_path.exists():
            self._error(f"No websocket/ or server/ subfolder found in: {self.sample_dir}")
            sys.exit(1)
        
        # Set configuration
        self.aws_region = args.region or os.getenv('AWS_REGION', 'us-east-1')
        self.account_id = args.account_id or os.getenv('ACCOUNT_ID')
        self.agent_name = args.agent_name or f"voice_workshop_{websocket_folder.replace('-', '_')}"
        
        if not self.account_id:
            self._error("ACCOUNT_ID is required. Set via --account-id or ACCOUNT_ID environment variable")
            sys.exit(1)
        
        self.config_file = self.sample_dir / "setup_config.json"

    def _print(self, message: str, color: str = Colors.NC):
        """Print colored message"""
        print(f"{color}{message}{Colors.NC}")

    def _error(self, message: str):
        """Print error message"""
        self._print(f"❌ {message}", Colors.RED)

    def _success(self, message: str):
        """Print success message"""
        self._print(f"✅ {message}", Colors.GREEN)

    def _info(self, message: str):
        """Print info message"""
        self._print(f"ℹ️  {message}", Colors.BLUE)

    def _warning(self, message: str):
        """Print warning message"""
        self._print(f"⚠️  {message}", Colors.YELLOW)

    def _run_command(self, cmd: list, cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
        """Run a shell command and return the result"""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            self._error(f"Command failed: {' '.join(cmd)}")
            self._error(f"Error: {e.stderr}")
            if check:
                raise
            return e

    def create_observability_destination(self) -> Optional[Dict]:
        """Create an AgentCore Observability destination for the strands agent."""
        if self.websocket_folder != 'strands-sonic':
            return None

        self._print("\n📊 Creating AgentCore Observability destination...", Colors.YELLOW)

        try:
            import boto3
            client = boto3.client('bedrock-agentcore-control', region_name=self.aws_region)

            destination_name = f"{self.agent_name}_observability"

            # Check if destination already exists
            try:
                response = client.list_observability_configurations()
                for dest in response.get('observabilityConfigurations', []):
                    if dest.get('name') == destination_name:
                        dest_id = dest['observabilityConfigurationId']
                        self._info(f"Found existing observability destination: {destination_name} (ID: {dest_id})")
                        # Get the full details to retrieve the OTLP endpoint
                        detail = client.get_observability_configuration(
                            observabilityConfigurationId=dest_id
                        )
                        otlp_endpoint = detail.get('otlpEndpoint', '')
                        return {
                            "destination_id": dest_id,
                            "destination_name": destination_name,
                            "otlp_endpoint": otlp_endpoint,
                        }
            except Exception:
                pass  # list may not be supported, proceed to create

            response = client.create_observability_configuration(
                name=destination_name,
                destinationType="CLOUDWATCH",
            )

            dest_id = response.get('observabilityConfigurationId', '')
            otlp_endpoint = response.get('otlpEndpoint', '')

            self._success(f"Observability destination created: {destination_name} (ID: {dest_id})")
            self._info(f"   OTLP endpoint: {otlp_endpoint}")

            return {
                "destination_id": dest_id,
                "destination_name": destination_name,
                "otlp_endpoint": otlp_endpoint,
            }

        except Exception as e:
            self._warning(f"Failed to create observability destination: {e}")
            self._info("You can create it manually and set OTEL_EXPORTER_OTLP_TRACES_ENDPOINT env var")
            return None

    def create_memory(self) -> Optional[Dict]:
        """Create an AgentCore Memory resource for the strands agent."""
        if self.websocket_folder != 'strands-sonic':
            return None

        self._print("\n🧠 Creating AgentCore Memory...", Colors.YELLOW)

        try:
            from bedrock_agentcore.memory import MemoryClient

            client = MemoryClient(region_name=self.aws_region)

            memory_name = f"{self.agent_name}_memory"

            # Check if memory already exists by listing and matching name
            try:
                existing = client.list_memories()
                # Handle different response formats
                memories_list = existing.get('memories', []) or existing.get('memorySummaries', []) or []
                if isinstance(existing, list):
                    memories_list = existing
                self._info(f"Found {len(memories_list)} existing memory resource(s)")
                for mem in memories_list:
                    mem_name = mem.get('name', '')
                    mem_id = mem.get('id', '') or mem.get('memoryId', '')
                    if mem_name == memory_name and mem_id:
                        self._info(f"Found existing memory: {memory_name} (ID: {mem_id})")
                        return {"memory_id": mem_id, "memory_name": memory_name}
            except Exception as e:
                self._info(f"Could not list memories: {e}")

            # Create new memory
            memory = client.create_memory(
                name=memory_name,
                description=f"Chat history for {self.agent_name}",
            )

            memory_id = memory.get('id') or memory.get('memoryId', '')
            self._success(f"Memory created: {memory_name} (ID: {memory_id})")

            return {"memory_id": memory_id, "memory_name": memory_name}

        except ImportError:
            self._warning("bedrock-agentcore package not installed, skipping memory creation")
            self._info("Install with: pip install bedrock-agentcore")
            return None
        except Exception as e:
            self._warning(f"Failed to create memory: {e}")
            self._info("You can create memory manually and set MEMORY_ID env var")
            return None

    def deploy_mcp_gateway(self) -> Optional[Dict]:
        """Deploy MCP Gateways (for strands-sonic and langchain-transcribe-polly agents that use MCP tools)"""
        if self.websocket_folder not in ('strands-sonic', 'langchain-transcribe-polly'):
            return None
        
        self._print("\n🌐 Deploying MCP Gateways...", Colors.YELLOW)
        
        # Initialize Gateway client
        client = GatewayClient(region_name=self.aws_region)
        bedrock_client = boto3.client('bedrock-agentcore-control', region_name=self.aws_region)
        
        # Define the four gateways to create
        gateway_configs = [
            {
                "name": "voice-workshop-faq-kb-tools",
                "mcp_server": "anybank-faq-kb",
                "tools": ["search_anybank_faq", "answer_anybank_question"]
            }
        ]
        
        deployed_gateways = []
        
        for gw_config in gateway_configs:
            gateway_name = gw_config["name"]
            self._print(f"\n📦 Deploying {gateway_name} gateway...", Colors.BLUE)
            
            gateway = None
            
            # Check if gateway already exists
            try:
                response = bedrock_client.list_gateways()
                for gw in response.get('items', []):
                    if gw.get('name') == gateway_name:
                        self._info(f"Found existing gateway: {gateway_name} (ID: {gw['gatewayId']})")
                        gateway_detail = bedrock_client.get_gateway(gatewayIdentifier=gw['gatewayId'])
                        gateway = gateway_detail
                        break
            except Exception as e:
                self._warning(f"Could not check for existing gateway: {e}")
            
            # Create MCP Gateway if it doesn't exist
            if not gateway:
                self._info(f"Creating {gateway_name} gateway...")
                try:
                    gateway = client.create_mcp_gateway(name=gateway_name)
                except Exception as e:
                    error_msg = str(e)
                    if "already exists" in error_msg.lower() or "conflict" in error_msg.lower():
                        self._warning(f"Gateway {gateway_name} already exists, fetching...")
                        response = bedrock_client.list_gateways()
                        for gw in response.get('items', []):
                            if gw.get('name') == gateway_name:
                                gateway_detail = bedrock_client.get_gateway(gatewayIdentifier=gw['gatewayId'])
                                gateway = gateway_detail
                                self._success(f"Retrieved existing gateway: {gw['gatewayId']}")
                                break
                        if not gateway:
                            raise Exception(f"Gateway '{gateway_name}' exists but could not be found")
                    else:
                        raise
            
            gateway_arn = gateway["gatewayArn"]
            gateway_url = gateway["gatewayUrl"]
            role_arn = gateway["roleArn"]
            gateway_id = gateway["gatewayId"]
            
            self._success(f"Gateway ready: {gateway_id}")
            self._info(f"   URL: {gateway_url}")
            
            # Create MCP Server Target
            self._info(f"Creating MCP Server Target for {gw_config['mcp_server']}...")
            
            try:
                target = client.create_mcp_gateway_target(
                    gateway=gateway,
                    name=gw_config["mcp_server"],
                    target_type="lambda",
                    target_payload=None
                )
                self._success(f"MCP Server target created: {target['targetId']}")
            except Exception as e:
                if "already exists" in str(e).lower() or "conflict" in str(e).lower():
                    self._warning(f"MCP Server target already exists for {gateway_name}, continuing...")
                    targets_response = bedrock_client.list_gateway_targets(gatewayIdentifier=gateway_id)
                    target = targets_response.get('items', [{}])[0] if targets_response.get('items') else {}
                else:
                    raise
            
            # Store gateway info
            deployed_gateways.append({
                "gateway_name": gateway_name,
                "gateway_id": gateway_id,
                "gateway_arn": gateway_arn,
                "gateway_url": gateway_url,
                "role_arn": role_arn,
                "target_id": target.get('targetId', 'unknown'),
                "mcp_server_name": gw_config["mcp_server"],
                "tools": gw_config["tools"]
            })
        
        # Save gateway configuration
        gateway_config = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "deployment_type": "mcp-gateway",
            "gateways": deployed_gateways,
            "aws": {
                "account_id": self.account_id,
                "region": self.aws_region
            }
        }
        
        config_path = self.sample_dir / "gateway_config.json"
        with open(config_path, "w") as f:
            json.dump(gateway_config, f, indent=2)
        
        self._success(f"Gateway configuration saved to {config_path}")
        self._info(f"   Deployed {len(deployed_gateways)} gateways")
        
        return {
            "gateways": deployed_gateways
        }

    def check_prerequisites(self):
        """Check if required tools are installed"""
        self._print("\n📋 Checking prerequisites...", Colors.YELLOW)
        
        required_tools = {
            'python3': 'Python 3.10+',
            'aws': 'AWS CLI',
            'agentcore': 'bedrock-agentcore-starter-toolkit'
        }
        
        missing_tools = []
        
        for tool, description in required_tools.items():
            if not shutil.which(tool):
                missing_tools.append(f"{tool} ({description})")
        
        if missing_tools:
            self._error("Missing required tools:")
            for tool in missing_tools:
                print(f"  - {tool}")
            print("\nInstall missing tools:")
            print("  pip install bedrock-agentcore-starter-toolkit")
            sys.exit(1)
        
        self._success("All prerequisites met")

    def setup_agentcore_project(self):
        """Set up AgentCore project structure"""
        self._print("\n📦 Setting up AgentCore project...", Colors.YELLOW)
        
        # Create .bedrock_agentcore.yaml configuration
        config = {
            'agent_name': self.agent_name,
            'region': self.aws_region,
            'entry_point': 'server.py',
            'runtime': 'python3.12',
            'bedrock_agentcore': {
                'agent_runtime_name': self.agent_name,
                'network_mode': 'PUBLIC'
            }
        }
        
        config_path = self.websocket_path / '.bedrock_agentcore.yaml'
        
        # Write configuration
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        self._success(f"Created AgentCore configuration: {config_path}")

    def create_iam_role(self) -> str:
        """Create IAM role for the agent"""
        self._print("\n🔐 Creating IAM role...", Colors.YELLOW)
        
        role_name = f"WebSocket{self.websocket_folder.replace('-', '_').capitalize()}AgentRole"
        
        # Read policy files early so they're available for both create and update paths
        deploy_dir = Path(__file__).parent
        agent_role_path = deploy_dir / 'agent_role.json'
        trust_policy_path = deploy_dir / 'trust_policy.json'
        
        if not agent_role_path.exists() or not trust_policy_path.exists():
            self._error("Policy files not found (agent_role.json, trust_policy.json)")
            sys.exit(1)
        
        # Check if role exists
        check_cmd = ['aws', 'iam', 'get-role', '--role-name', role_name]
        result = self._run_command(check_cmd, check=False)
        
        if result.returncode == 0:
            role_data = json.loads(result.stdout)
            role_arn = role_data['Role']['Arn']
            self._info(f"IAM role {role_name} already exists")
            
            # Always update the policy to ensure latest permissions are applied
            with open(agent_role_path, 'r') as f:
                agent_role_policy = f.read().replace('${ACCOUNT_ID}', self.account_id)
            
            put_policy_cmd = [
                'aws', 'iam', 'put-role-policy',
                '--role-name', role_name,
                '--policy-name', f'{role_name}Policy',
                '--policy-document', agent_role_policy
            ]
            self._run_command(put_policy_cmd)
            self._success(f"Updated policy on existing role: {role_arn}")
            return role_arn
        
        # Read and substitute ACCOUNT_ID in agent_role.json
        with open(agent_role_path, 'r') as f:
            agent_role_policy = f.read().replace('${ACCOUNT_ID}', self.account_id)
        
        # Create role
        create_role_cmd = [
            'aws', 'iam', 'create-role',
            '--role-name', role_name,
            '--assume-role-policy-document', f'file://{trust_policy_path}',
            '--output', 'json'
        ]
        
        result = self._run_command(create_role_cmd)
        self._success("Role created")
        
        # Attach policy
        put_policy_cmd = [
            'aws', 'iam', 'put-role-policy',
            '--role-name', role_name,
            '--policy-name', f'{role_name}Policy',
            '--policy-document', agent_role_policy
        ]
        
        self._run_command(put_policy_cmd)
        self._success("Policy attached")
        
        # Get role ARN
        result = self._run_command(['aws', 'iam', 'get-role', '--role-name', role_name, '--output', 'json'])
        role_data = json.loads(result.stdout)
        role_arn = role_data['Role']['Arn']
        
        self._success(f"IAM role created: {role_arn}")
        
        # Wait for IAM propagation
        self._info("Waiting 10 seconds for IAM role to propagate...")
        time.sleep(10)
        
        return role_arn

    def deploy_agent(self, role_arn: str, gateway_info: Optional[Dict] = None, memory_info: Optional[Dict] = None, observability_info: Optional[Dict] = None) -> Dict:
        """Deploy agent using starter toolkit"""
        self._print("\n🚀 Deploying agent to AgentCore Runtime...", Colors.YELLOW)
        
        # Change to websocket directory
        original_dir = Path.cwd()
        os.chdir(self.websocket_path)
        
        try:
            # Remove any existing configuration file first
            config_path = Path('.bedrock_agentcore.yaml')
            if config_path.exists():
                self._info("Removing existing configuration...")
                config_path.unlink()
            
            # Create .bedrock_agentcore.yaml configuration file directly
            self._info("Creating AgentCore configuration...")
            
            # The toolkit expects an 'agents' section with agent definitions
            # Use ecr_auto_create to let the SDK create the repository and get the full URI
            config = {
                'agents': {
                    self.agent_name: {
                        'name': self.agent_name,
                        'entrypoint': 'server.py',
                        'runtime': 'python3.12',
                        'aws': {
                            'account': self.account_id,
                            'region': self.aws_region,
                            'execution_role': role_arn,
                            'ecr_auto_create': True
                        }
                    }
                },
                'default_agent': self.agent_name,
                'region': self.aws_region
            }
            
            # Prepare environment variables
            env_vars = {}
            
            # Add MCP Gateway environment variables if available (for strands-sonic and langchain-transcribe-polly)
            if self.websocket_folder in ('strands-sonic', 'langchain-transcribe-polly') and gateway_info:
                gateways = gateway_info.get('gateways', [])
                
                if gateways:
                    # Pass all gateway ARNs and URLs as JSON-encoded environment variables
                    gateway_arns = [gw['gateway_arn'] for gw in gateways]
                    gateway_urls = [gw['gateway_url'] for gw in gateways]
                    
                    env_vars['MCP_GATEWAY_ARNS'] = json.dumps(gateway_arns)
                    env_vars['MCP_GATEWAY_URLS'] = json.dumps(gateway_urls)
                    
                    self._info(f"Added MCP Gateway environment variables for {len(gateways)} gateways")
                    for gw in gateways:
                        self._info(f"   {gw['gateway_name']}: {gw['gateway_url']}")

            # Add AgentCore Memory environment variable if available (for strands-sonic-sonic)
            if memory_info and memory_info.get('memory_id'):
                env_vars['MEMORY_ID'] = memory_info['memory_id']
                env_vars['MEMORY_REGION'] = self.aws_region
                self._info(f"Added MEMORY_ID={memory_info['memory_id']} to environment")
            elif self.websocket_folder == 'strands-sonic':
                # Fallback: check setup_config.json from previous deployment
                try:
                    if self.config_file.exists():
                        with open(self.config_file, 'r') as f:
                            prev_config = json.load(f)
                        prev_memory_id = prev_config.get('memory', {}).get('memory_id')
                        if prev_memory_id:
                            env_vars['MEMORY_ID'] = prev_memory_id
                            env_vars['MEMORY_REGION'] = self.aws_region
                            self._info(f"Added MEMORY_ID={prev_memory_id} from previous config")
                except Exception:
                    pass

            # Add Observability environment variables if available (for strands-sonic-sonic)
            if observability_info and observability_info.get('otlp_endpoint'):
                env_vars['OTEL_EXPORTER_OTLP_TRACES_ENDPOINT'] = observability_info['otlp_endpoint']
                env_vars['OTEL_SERVICE_NAME'] = self.agent_name
                self._info(f"Added OTEL_EXPORTER_OTLP_TRACES_ENDPOINT to environment")

            # Add Pipecat-specific environment variables from .env file (if any)
            if self.websocket_folder == 'pipecat-sonic':
                env_file = self.websocket_path / '.env'
                if env_file.exists():
                    self._info("Loading Pipecat environment variables from .env file...")
                    with open(env_file) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, _, value = line.partition('=')
                                key, value = key.strip(), value.strip()
                                if value:
                                    env_vars[key] = value
                                    self._info(f"   {key}: ***configured***")
            
            # Write env vars into the config so the toolkit picks them up
            if env_vars:
                config['agents'][self.agent_name]['environment_variables'] = env_vars
                self._info(f"Wrote {len(env_vars)} environment variable(s) to config")

            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            self._success(f"Configuration created: {config_path}")
            
            # Determine deployment mode
            local = self.args.local
            use_codebuild = not self.args.local_build
            
            if local:
                self._info("Deploying with local mode (requires Docker)")
            elif not use_codebuild:
                self._info("Deploying with local build mode (requires Docker)")
            else:
                self._info("Deploying with CodeBuild (no Docker required)")
            
            self._info("Launching agent (this may take a few minutes)...")
            
            # Use starter toolkit to launch
            result = launch_bedrock_agentcore(
                config_path=config_path,
                agent_name=self.agent_name,
                local=local,
                use_codebuild=use_codebuild,
                env_vars=env_vars,
                auto_update_on_conflict=True
            )
            
            # Extract agent information from result
            agent_arn = result.agent_arn
            agent_id = result.agent_id
            
            if not agent_arn:
                raise RuntimeError("Failed to get agent ARN from deployment result")
            
            self._success(f"Agent deployed successfully!")
            self._info(f"   Agent ARN: {agent_arn}")
            self._info(f"   Agent ID: {agent_id}")
            
            # Post-deploy: ensure environment variables are set on the runtime
            # The toolkit may not apply env_vars on updates, so we force-set them
            # Also check setup_config.json for memory ID if not in env_vars
            if 'MEMORY_ID' not in env_vars and self.websocket_folder == 'strands-sonic':
                try:
                    if self.config_file.exists():
                        with open(self.config_file, 'r') as f:
                            prev_config = json.load(f)
                        prev_memory_id = prev_config.get('memory', {}).get('memory_id')
                        if prev_memory_id:
                            env_vars['MEMORY_ID'] = prev_memory_id
                            env_vars['MEMORY_REGION'] = self.aws_region
                            self._info(f"Added MEMORY_ID={prev_memory_id} from previous config")
                except Exception:
                    pass

            if env_vars:
                try:
                    self._info("Updating runtime environment variables...")
                    bedrock_client = boto3.client('bedrock-agentcore-control', region_name=self.aws_region)
                    bedrock_client.update_agent_runtime(
                        agentRuntimeId=agent_id,
                        environmentVariables=env_vars,
                    )
                    self._success(f"Environment variables updated ({len(env_vars)} vars)")
                    for key in env_vars:
                        val_preview = env_vars[key][:50] + "..." if len(env_vars[key]) > 50 else env_vars[key]
                        self._info(f"   {key}={val_preview}")
                except Exception as e:
                    self._warning(f"Failed to update env vars (may already be set): {e}")

            return {
                'agent_arn': agent_arn,
                'agent_runtime_name': self.agent_name,
                'role_arn': role_arn
            }
            
        finally:
            os.chdir(original_dir)

    def deploy_subagents(self, role_arn: str) -> Optional[list]:
        """Deploy A2A sub-agents to AgentCore Runtime (only for strands-sonic)"""
        if self.websocket_folder != 'strands-sonic':
            return None

        subagents_dir = self.sample_dir / "subagents"
        if not subagents_dir.exists():
            self._info("No subagents directory found, skipping A2A deployment")
            return None

        subagent_configs = [
            {"name": "voice_workshop_auth_agent", "folder": "auth_agent"},
            {"name": "voice_workshop_banking_agent", "folder": "banking_agent"},
            {"name": "voice_workshop_mortgage_agent", "folder": "mortgage_agent"},
        ]

        self._print("\n🤖 Deploying A2A Sub-Agents...", Colors.BLUE)

        deployed_subagents = []
        for sa_config in subagent_configs:
            sa_name = sa_config["name"]
            sa_folder = subagents_dir / sa_config["folder"]

            if not sa_folder.exists():
                self._info(f"Sub-agent folder not found: {sa_folder}, skipping")
                continue

            self._print(f"\n📦 Deploying {sa_name}...", Colors.BLUE)

            try:
                original_dir = os.getcwd()
                os.chdir(str(sa_folder))

                # Create .bedrock_agentcore.yaml for A2A agent
                ecr_repo = f"{self.account_id}.dkr.ecr.{self.aws_region}.amazonaws.com/bedrock-agentcore-{sa_name}"
                
                # Pre-create ECR repository
                try:
                    import boto3
                    ecr_client = boto3.client('ecr', region_name=self.aws_region)
                    repo_name = f"bedrock-agentcore-{sa_name}"
                    try:
                        ecr_client.create_repository(repositoryName=repo_name)
                        self._success(f"ECR repository created: {repo_name}")
                    except ecr_client.exceptions.RepositoryAlreadyExistsException:
                        self._info(f"ECR repository already exists: {repo_name}")
                except Exception as e:
                    self._info(f"ECR pre-creation skipped: {e}")

                a2a_config = {
                    'agents': {
                        sa_name: {
                            'name': sa_name,
                            'entrypoint': 'main.py',
                            'runtime': 'python3.12',
                            'aws': {
                                'account': self.account_id,
                                'region': self.aws_region,
                                'execution_role': role_arn,
                                'ecr_repository': ecr_repo,
                                'ecr_auto_create': True,
                                'network_configuration': {
                                    'network_mode': 'PUBLIC'
                                },
                                'protocol_configuration': {
                                    'server_protocol': 'A2A'
                                }
                            }
                        }
                    },
                    'default_agent': sa_name,
                    'region': self.aws_region
                }

                config_path = Path('.bedrock_agentcore.yaml')
                with open(config_path, 'w') as f:
                    yaml.dump(a2a_config, f, default_flow_style=False)

                # Deploy using starter toolkit
                result = launch_bedrock_agentcore(
                    config_path=config_path,
                    agent_name=sa_name,
                    local=False,
                    use_codebuild=True,
                    auto_update_on_conflict=True
                )

                agent_arn = result.get('agent_arn', '') if isinstance(result, dict) else str(result)
                self._success(f"Sub-agent deployed: {sa_name}")
                self._info(f"   ARN: {agent_arn}")

                deployed_subagents.append({
                    "name": sa_name,
                    "folder": sa_config["folder"],
                    "agent_arn": agent_arn,
                })

            except Exception as e:
                self._error(f"Failed to deploy sub-agent {sa_name}: {e}")
                import traceback
                traceback.print_exc()
            finally:
                os.chdir(original_dir)

        if deployed_subagents:
            self._success(f"Deployed {len(deployed_subagents)} A2A sub-agent(s)")

        return deployed_subagents if deployed_subagents else None

    def save_configuration(self, deployment_info: Dict):
        """Save deployment configuration to JSON file"""
        self._print("\n💾 Saving configuration...", Colors.YELLOW)
        
        config = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'websocket_folder': self.websocket_folder,
            'aws_region': self.aws_region,
            'account_id': self.account_id,
            'agent_name': self.agent_name,
            'agent_runtime_name': deployment_info['agent_runtime_name'],
            'agent_arn': deployment_info['agent_arn'],
            'iam_role_arn': deployment_info['role_arn'],
            'deployment_method': 'agentcore-starter-toolkit'
        }

        # Include memory info if available
        if 'memory' in deployment_info:
            config['memory'] = deployment_info['memory']

        # Include observability info if available
        if 'observability' in deployment_info:
            config['observability'] = deployment_info['observability']
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        self._success(f"Configuration saved to {self.config_file}")

    def print_summary(self, deployment_info: Dict):
        """Print deployment summary"""
        self._print("\n" + "="*80, Colors.GREEN)
        self._print("✅ Deployment Complete!", Colors.GREEN)
        self._print("="*80, Colors.GREEN)
        
        self._print("\n📊 Configuration Summary", Colors.BLUE)
        self._print("="*80, Colors.GREEN)
        
        print(f"\n{Colors.YELLOW}AWS Configuration:{Colors.NC}")
        print(f"   Account ID:        {self.account_id}")
        print(f"   Region:            {self.aws_region}")
        
        print(f"\n{Colors.YELLOW}Agent Runtime:{Colors.NC}")
        print(f"   Agent Name:        {deployment_info['agent_runtime_name']}")
        print(f"   Agent ARN:         {deployment_info['agent_arn']}")
        print(f"   IAM Role:          {deployment_info['role_arn']}")
        
        # Show gateway info if available (strands deployment)
        if 'gateways' in deployment_info:
            gateways = deployment_info['gateways']
            print(f"\n{Colors.YELLOW}MCP Gateways ({len(gateways)} deployed):{Colors.NC}")
            for gw in gateways:
                print(f"\n   {gw['gateway_name']}:")
                print(f"      Gateway ID:     {gw['gateway_id']}")
                print(f"      Gateway URL:    {gw['gateway_url']}")
                print(f"      Target ID:      {gw['target_id']}")
                print(f"      Tools:          {', '.join(gw['tools'])}")

        # Show memory info if available (strands deployment)
        if 'memory' in deployment_info:
            mem = deployment_info['memory']
            print(f"\n{Colors.YELLOW}AgentCore Memory:{Colors.NC}")
            print(f"   Memory ID:         {mem.get('memory_id', 'N/A')}")
            print(f"   Memory Name:       {mem.get('memory_name', 'N/A')}")

        # Show observability info if available (strands deployment)
        if 'observability' in deployment_info:
            obs = deployment_info['observability']
            print(f"\n{Colors.YELLOW}AgentCore Observability:{Colors.NC}")
            print(f"   Destination ID:    {obs.get('destination_id', 'N/A')}")
            print(f"   Destination Name:  {obs.get('destination_name', 'N/A')}")
            print(f"   OTLP Endpoint:     {obs.get('otlp_endpoint', 'N/A')}")

        # Show sub-agent info if available (strands deployment)
        if 'subagents' in deployment_info:
            subagents = deployment_info['subagents']
            print(f"\n{Colors.YELLOW}A2A Sub-Agents ({len(subagents)} deployed):{Colors.NC}")
            for sa in subagents:
                print(f"\n   {sa['name']}:")
                print(f"      ARN: {sa['agent_arn']}")
        
        self._print("\n" + "="*80, Colors.GREEN)
        self._print("\n🚀 Next Steps", Colors.BLUE)
        self._print("="*80, Colors.GREEN)
        
        print(f"\n{Colors.YELLOW}1. Start the client:{Colors.NC}")
        print(f"   ./deployment/agentcore/start_client.sh {self.websocket_folder}")
        
        print(f"\n{Colors.YELLOW}2. Or test with agentcore CLI:{Colors.NC}")
        print(f'   agentcore invoke "Hello!"')
        
        print(f"\n{Colors.YELLOW}3. View logs:{Colors.NC}")
        print(f"   Check CloudWatch Logs in AWS Console")
        
        print(f"\n{Colors.YELLOW}4. When done, clean up:{Colors.NC}")
        print(f"   python deployment/agentcore/cleanup.py {self.websocket_folder}")
        
        self._print("\n" + "="*80, Colors.GREEN)

    def deploy(self):
        """Main deployment workflow"""
        try:
            self._print(f"\n🚀 AgentCore Deployment - {self.websocket_folder}", Colors.BLUE)
            self._print(f"📁 Using websocket folder: {self.websocket_folder}\n", Colors.BLUE)
            
            # Step 1: Check prerequisites
            self.check_prerequisites()
            
            # Step 1.5: Deploy MCP Gateway (only for strands-sonic)
            gateway_info = None
            if not getattr(self.args, 'skip_gateway', False):
                gateway_info = self.deploy_mcp_gateway()
            else:
                self._info("Skipping MCP Gateway deployment (--skip-gateway)")

            # Step 1.6: Create AgentCore Memory (only for strands-sonic)
            memory_info = None
            if not getattr(self.args, 'skip_memory', False):
                memory_info = self.create_memory()
            else:
                self._info("Skipping AgentCore Memory creation (--skip-memory)")

            # Step 1.7: Create Observability destination (only for strands-sonic)
            observability_info = self.create_observability_destination()
            
            # Step 2: Create IAM role
            role_arn = self.create_iam_role()
            
            # Step 3: Deploy agent
            deployment_info = self.deploy_agent(role_arn, gateway_info, memory_info, observability_info)
            
            # Step 3.5: Deploy A2A sub-agents (only for strands-sonic)
            subagent_info = self.deploy_subagents(role_arn)
            
            # Add gateway info to deployment info if available
            if gateway_info:
                deployment_info['gateway'] = gateway_info

            # Add memory info to deployment info if available
            if memory_info:
                deployment_info['memory'] = memory_info

            # Add observability info to deployment info if available
            if observability_info:
                deployment_info['observability'] = observability_info

            # Add sub-agent info to deployment info if available
            if subagent_info:
                deployment_info['subagents'] = subagent_info
            
            # Step 4: Save configuration
            self.save_configuration(deployment_info)
            
            # Step 5: Print summary
            self.print_summary(deployment_info)
            
        except KeyboardInterrupt:
            self._error("\nDeployment cancelled by user")
            sys.exit(1)
        except Exception as e:
            self._error(f"Deployment failed: {e}")
            traceback.print_exc()
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Deploy agents to Amazon Bedrock AgentCore Runtime using starter toolkit',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy.py bedrock-sonic
  python deploy.py strands-sonic --region us-west-2
  python deploy.py langchain-transcribe-polly --agent-name my-langchain-agent
  python deploy.py bedrock-sonic --agent-name my-sonic-agent --local-build

Environment Variables:
  ACCOUNT_ID    AWS Account ID (required if not provided via --account-id)
  AWS_REGION    AWS Region (default: us-east-1)
        """
    )
    
    parser.add_argument(
        'websocket_folder',
        choices=['bedrock-sonic', 'strands-sonic', 'langchain-transcribe-polly', 'pipecat-sonic', 'echo', 'webrtc-kvs-sonic'],
        help='Websocket folder to deploy (bedrock-sonic, strands-sonic, langchain-transcribe-polly, pipecat-sonic, echo, or webrtc-kvs-sonic)'
    )
    
    parser.add_argument(
        '--account-id',
        help='AWS Account ID (or set ACCOUNT_ID env var)'
    )
    
    parser.add_argument(
        '--region',
        help='AWS Region (default: us-east-1 or AWS_REGION env var)'
    )
    
    parser.add_argument(
        '--agent-name',
        help='Custom agent name (default: bidi_<folder>_agent)'
    )
    
    parser.add_argument(
        '--local',
        action='store_true',
        help='Build and run locally (requires Docker)'
    )
    
    parser.add_argument(
        '--local-build',
        action='store_true',
        help='Build locally, deploy to cloud (requires Docker)'
    )
    
    parser.add_argument(
        '--skip-gateway',
        action='store_true',
        help='Skip MCP Gateway deployment (deploy runtime only)'
    )
    
    parser.add_argument(
        '--skip-memory',
        action='store_true',
        help='Skip AgentCore Memory creation'
    )
    
    args = parser.parse_args()
    
    # Create deployer and run
    deployer = AgentCoreDeployer(args.websocket_folder, args)
    deployer.deploy()


if __name__ == '__main__':
    main()
