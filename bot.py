import logging
import subprocess
import sys
import os
import re
import time
import concurrent.futures
import random
import discord
from discord.ext import commands, tasks
import docker
import asyncio
from discord import app_commands
import requests

# Set Your Bot Token gay
TOKEN = '
RAM_LIMIT = '2g' #Set Your Own Ram How Much You Want To Give Your Users
SERVER_LIMIT = 2 #you can change it!
database_file = 'database.txt'

intents = discord.Intents.default()
intents.messages = False
intents.message_content = False

bot = commands.Bot(command_prefix='/', intents=intents)
client = docker.from_env()

whitelist_ids = {"1128161197766746213"}  # Replace with actual user IDs

# Utility Functions
def add_to_database(userid, container_name, ssh_command):
    with open(database_file, 'a') as f:
        f.write(f"{userid}|{container_name}|{ssh_command}\n")

def remove_from_database(ssh_command):
    if not os.path.exists(database_file):
        return
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            if ssh_command not in line:
                f.write(line)

def get_user_servers(user):
    if not os.path.exists(database_file):
        return []
    servers = []
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user):
                servers.append(line.strip())
    return servers

def count_user_servers(userid):
    return len(get_user_servers(userid))

def get_container_id_from_database(userid, container_name):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(userid) and container_name in line:
                return line.split('|')[1]
    return None

def generate_random_port():
    return random.randint(1025, 65535)

async def capture_ssh_session_line(process):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        output = output.decode('utf-8').strip()
        if "ssh session:" in output:
            return output.split("ssh session:")[1].strip()
    return None



# In-memory database for user credits
user_credits = {}

# Cuty.io API key (Your account key)
API_KEY = 'ebe681f9e37ef61fcfd756396'

# Slash command: earnCredit
@bot.tree.command(name="earncredit", description="Generate a URL to shorten and earn credits.")
async def earncredit(interaction: discord.Interaction):
    print("Received request to shorten URL")
    user_id = interaction.user.id

    # Define a default URL to shorten
    default_url = "https://cuty.io/e58WUzLMmE3S"  # Change this as needed

    # Make a request to Cuty.io API to shorten the default URL
    api_url = f"https://cutt.ly/api/api.php?key={API_KEY}&short={default_url}"
    print(f"Making API call to: {api_url}")
    response = requests.get(api_url).json()
    print(f"API response: {response}")

    # Check if the URL was successfully shortened
    if response['url']['status'] == 7:
        shortened_url = response['url']['shortLink']
        credits_earned = 1  # Update to 1 credit for each shortening

        # Add credits to user
        user_credits[user_id] = user_credits.get(user_id, 0) + credits_earned

        await interaction.response.send_message(f"Success! Here's your shortened URL: {shortened_url}. You earned {credits_earned} credit!")
    else:
        # Handle API error messages
        error_message = response['url'].get('title', 'Failed to generate a shortened URL. Please try again.')
        await interaction.response.send_message(error_message)

# Slash command: bal
@bot.tree.command(name="bal", description="Check your credit balance.")
async def bal(interaction: discord.Interaction):
    user_id = interaction.user.id
    credits = user_credits.get(user_id, 0)
    await interaction.response.send_message(f"You have {credits} credits.")


# Node Status Command
def get_node_status():
    try:
        containers = client.containers.list(all=True)
        container_status = "\n".join([f"{container.name} - {container.status}" for container in containers]) or "No containers running."

        # Get system-wide memory usage using `os` module
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
        mem_total = int(re.search(r'MemTotal:\s+(\d+)', meminfo).group(1)) / 1024  # Convert to MB
        mem_free = int(re.search(r'MemFree:\s+(\d+)', meminfo).group(1)) / 1024  # Convert to MB
        mem_available = int(re.search(r'MemAvailable:\s+(\d+)', meminfo).group(1)) / 1024  # Convert to MB

        memory_used = mem_total - mem_available
        memory_percentage = (memory_used / mem_total) * 100 if mem_total else 0

        node_info = {
            "containers": container_status,
            "memory_total": mem_total,
            "memory_used": memory_used,
            "memory_percentage": memory_percentage
        }
        return node_info
    except Exception as e:
        return str(e)

@bot.tree.command(name="node", description="Show the current status of the VPS node.")
async def node_status(interaction: discord.Interaction):
    try:
        node_info = get_node_status()

        if isinstance(node_info, str):  # If there's an error
            await interaction.response.send_message(embed=discord.Embed(description=f"### Error fetching node status: {node_info}", color=0xff0000))
            return

        # Format the status message
        embed = discord.Embed(title="VPS Node1 Status", color=0x00ff00)
        embed.add_field(name="Containers", value=node_info["containers"], inline=False)
        embed.add_field(name="Memory Usage", value=f"{node_info['memory_used']:.2f} / {node_info['memory_total']:.2f} MB ({node_info['memory_percentage']:.2f}%)", inline=False)

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"### Failed to fetch node status: {str(e)}", color=0xff0000))


@bot.tree.command(name="renew", description="Renew a VPS for 8 days using 2 credits.")
@app_commands.describe(vps_id="ID of the VPS to renew")
async def renew(interaction: discord.Interaction, vps_id: str):
    user_id = str(interaction.user.id)
    credits = user_credits.get(user_id, 0)

    # Check if user has enough credits
    if credits < 2:
        await interaction.response.send_message(embed=discord.Embed(
            description="You don't have enough credits to renew the VPS. You need 2 credits.",
            color=0xff0000))
        return

    # Get VPS from the database (check if VPS exists for the user)
    container_id = get_container_id_from_database(user_id, vps_id)
    if not container_id:
        await interaction.response.send_message(embed=discord.Embed(
            description=f"VPS with ID {vps_id} not found.",
            color=0xff0000))
        return

    # Deduct credits
    user_credits[user_id] -= 2

    # Renew VPS: Add 8 days to the current expiry
    renewal_date = datetime.now() + timedelta(days=8)
    vps_renewals[vps_id] = renewal_date

    # You may also want to log this in a persistent database, not just in memory

    await interaction.response.send_message(embed=discord.Embed(
        description=f"VPS {vps_id} has been renewed for 8 days. New expiry date: {renewal_date.strftime('%Y-%m-%d')}. "
                    f"You now have {user_credits[user_id]} credits remaining.",
        color=0x00ff00))


# Remove Everything Task
async def remove_everything_task(interaction: discord.Interaction):
    await interaction.channel.send("### Node is full. Resetting all user instances...")
    try:
        subprocess.run("docker rm -f $(sudo docker ps -a -q)", shell=True, check=True)
        os.remove(database_file)
        subprocess.run("pkill pytho*", shell=True, check=True)
        await interaction.channel.send("### All instances and data have been reset.")
    except Exception as e:
        await interaction.channel.send(f"### Failed to reset instances: {str(e)}")

# KillVPS Command (Admin only)
@bot.tree.command(name="killvps", description="Kill all user VPS instances. Admin only.")
async def kill_vps(interaction: discord.Interaction):
    userid = str(interaction.user.id)
    if userid not in whitelist_ids:
        await interaction.response.send_message(embed=discord.Embed(description="You do not have permission to use this command.", color=0xff0000))
        return

    await remove_everything_task(interaction)
    await interaction.response.send_message(embed=discord.Embed(description="### All user VPS instances have been terminated.", color=0x00ff00))

def add_to_database(userid, container_name, ssh_command):
    with open(database_file, 'a') as f:
        f.write(f"{userid}|{container_name}|{ssh_command}\n")

def remove_from_database(ssh_command):
    if not os.path.exists(database_file):
        return
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            if ssh_command not in line:
                f.write(line)

async def capture_ssh_session_line(process):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        output = output.decode('utf-8').strip()
        if "ssh session:" in output:
            return output.split("ssh session:")[1].strip()
    return None

whitelist_ids = {"1128161197766746213"}  # Replace with actual user IDs

@bot.tree.command(name="remove-everything", description="Removes all data and containers")
async def remove_everything(interaction: discord.Interaction):
    userid = str(interaction.user.id)
    if userid not in whitelist_ids:
        await interaction.response.send_message(embed=discord.Embed(description="You do not have permission to use this command.", color=0xff0000))
        return

    # Remove all Docker containers
    try:
        subprocess.run("docker rm -f $(sudo docker ps -a -q)", shell=True, check=True)
        await interaction.response.send_message(embed=discord.Embed(description="All Docker containers have been removed.", color=0x00ff00))
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description="Failed to remove Docker containers.", color=0xff0000))

    # Remove database and port files
    try:
        os.remove(database_file)
        os.remove(port_db_file)
        await interaction.response.send_message(embed=discord.Embed(description="Database and port files have been cleared. Service has been restarted. Please start the bot in the shell", color=0x00ff00))
        subprocess.run("pkill pytho*", shell=True, check=True)
    except Exception as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"Failed to clear database or restart service: {str(e)}", color=0xff0000))

#@tasks.loop(seconds=5)
#async def change_status():
#    try:
#        if os.path.exists(database_file):
#            with open(database_file, 'r') as f:
#                lines = f.readlines()
#                instance_count = len(lines)
#        else:
#            instance_count = 0
#
#        status = f"with {instance_count} Cloud Instances"
#        await bot.change_presence(activity=discord.Game(name=status))
#    except Exception as e:
#        print(f"Failed to update status: {e}")

def get_ssh_command_from_database(container_id):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if container_id in line:
                return line.split('|')[2]
    return None

def get_user_servers(user):
    if not os.path.exists(database_file):
        return []
    servers = []
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user):
                servers.append(line.strip())
    return servers

def count_user_servers(userid):
    return len(get_user_servers(userid))

def get_container_id_from_database(userid):
    servers = get_user_servers(userid)
    if servers:
        return servers[0].split('|')[1]
    return None

@bot.event
async def on_ready():
    #change_status.start()
    print(f'Bot is ready. Logged in as {bot.user}')
    await bot.tree.sync()

async def regen_ssh_command(interaction: discord.Interaction, container_name: str):
#    await interaction.response.defer()
    user = str(interaction.user)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:
        await interaction.response.send_message(embed=discord.Embed(description="### No active instance found for your user.", color=0xff0000))
        return

    try:
        exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_id, "tmate", "-F",
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"Error executing tmate in Docker container: {e}", color=0xff0000))
        return

    ssh_session_line = await capture_ssh_session_line(exec_cmd)
    if ssh_session_line:
        await interaction.user.send(embed=discord.Embed(description=f"### New SSH Session Command: ```{ssh_session_line}```", color=0x00ff00))
        await interaction.response.send_message(embed=discord.Embed(description="### New SSH session generated. Check your DMs for details.", color=0x00ff00))
    else:
        await interaction.response.send_message(embed=discord.Embed(description="### Failed to generate new SSH session.", color=0xff0000))

async def start_server(interaction: discord.Interaction, container_name: str):
#    await interaction.response.defer()
    userid = str(interaction.user.id)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:
        await interaction.response.send_message(embed=discord.Embed(description="### No instance found for your user.", color=0xff0000))
        return

    try:
        subprocess.run(["docker", "start", container_id], check=True)
        exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_id, "tmate", "-F",
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        ssh_session_line = await capture_ssh_session_line(exec_cmd)
        if ssh_session_line:
            await interaction.user.send(embed=discord.Embed(description=f"### Instance Started\nSSH Session Command: ```{ssh_session_line}```", color=0x00ff00))
            await interaction.response.send_message(embed=discord.Embed(description="### Instance started successfully. Check your DMs for details.", color=0x00ff00))
        else:
            await interaction.response.send_message(embed=discord.Embed(description="### Instance started, but failed to get SSH session line.", color=0xff0000))
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"Error starting instance: {e}", color=0xff0000))

async def stop_server(interaction: discord.Interaction, container_name: str):
#    await interaction.response.defer()
    userid = str(interaction.user.id)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:
        await interaction.response.send_message(embed=discord.Embed(description="### No instance found for your user.", color=0xff0000))
        return

    try:
        subprocess.run(["docker", "stop", container_id], check=True)
        await interaction.response.send_message(embed=discord.Embed(description="### Instance stopped successfully.", color=0x00ff00))
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"### Error stopping instance: {e}", color=0xff0000))

async def restart_server(interaction: discord.Interaction, container_name: str):
#    await interaction.response.defer()
    userid = str(interaction.user.id)
    container_id = get_container_id_from_database(userid, container_name)

    if not container_id:
        await interaction.response.send_message(embed=discord.Embed(description="### No instance found for your user.", color=0xff0000))
        return

    try:
        subprocess.run(["docker", "restart", container_id], check=True)
        exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_id, "tmate", "-F",
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        ssh_session_line = await capture_ssh_session_line(exec_cmd)
        if ssh_session_line:
            await interaction.user.send(embed=discord.Embed(description=f"### Instance Restarted\nSSH Session Command: ```{ssh_session_line}```\nOS: Ubuntu 22.04", color=0x00ff00))
            await interaction.response.send_message(embed=discord.Embed(description="### Instance restarted successfully. Check your DMs for details.", color=0x00ff00))
        else:
            await interaction.response.send_message(embed=discord.Embed(description="### Instance restarted, but failed to get SSH session line.", color=0xff0000))
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"Error restarting instance: {e}", color=0xff0000))

def get_container_id_from_database(userid, container_name):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(userid) and container_name in line:
                return line.split('|')[1]
    return None

def generate_random_port():
    return random.randint(1025, 65535)

async def create_server_task(interaction):
    await interaction.response.send_message(embed=discord.Embed(description="### Creating Instance, This takes a few seconds. Powered by [CrashOfGuys](<https://discord.com/invite/VWm8zUEQN8>)", color=0x00ff00))
    userid = str(interaction.user.id)
    if count_user_servers(userid) >= SERVER_LIMIT:
        await interaction.followup.send(embed=discord.Embed(description="```Error: Instance Limit-reached```", color=0xff0000))
        return

    image = "ubuntu-22.04-with-tmate"

    try:
        container_id = subprocess.check_output([
            "docker", "run", "-itd", "--privileged", "--cap-add=ALL", image
        ]).strip().decode('utf-8')
    except subprocess.CalledProcessError as e:
        await interaction.followup.send(embed=discord.Embed(description=f"### Error creating Docker container: {e}", color=0xff0000))
        return

    try:
        exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_id, "tmate", "-F",
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        await interaction.followup.send(embed=discord.Embed(description=f"### Error executing tmate in Docker container: {e}", color=0xff0000))
        subprocess.run(["docker", "kill", container_id])
        subprocess.run(["docker", "rm", container_id])
        return

    ssh_session_line = await capture_ssh_session_line(exec_cmd)
    if ssh_session_line:
        await interaction.user.send(embed=discord.Embed(description=f"### Successfully created Instance\nSSH Session Command: ```{ssh_session_line}```\nOS: Ubuntu 22.04\nPassword: root", color=0x00ff00))
        add_to_database(userid, container_id, ssh_session_line)
        await interaction.followup.send(embed=discord.Embed(description="### Instance created successfully. Check your DMs for details.", color=0x00ff00))
    else:
        await interaction.followup.send(embed=discord.Embed(description="### Something went wrong or the Instance is taking longer than expected. If this problem continues, Contact Support.", color=0xff0000))
        subprocess.run(["docker", "kill", container_id])
        subprocess.run(["docker", "rm", container_id])

@bot.tree.command(name="deploy", description="Creates a new Instance with Ubuntu 22.04")
async def deploy_ubuntu(interaction: discord.Interaction):
    await create_server_task(interaction)

#@bot.tree.command(name="deploy-debian", description="Creates a new Instance with Debian 12")
#async def deploy_ubuntu(interaction: discord.Interaction):
#    await create_server_task_debian(interaction)

@bot.tree.command(name="regen-ssh", description="Generates a new SSH session for your instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def regen_ssh(interaction: discord.Interaction, container_name: str):
    await regen_ssh_command(interaction, container_name)

@bot.tree.command(name="start", description="Starts your instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def start(interaction: discord.Interaction, container_name: str):
    await start_server(interaction, container_name)

@bot.tree.command(name="stop", description="Stops your instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def stop(interaction: discord.Interaction, container_name: str):
    await stop_server(interaction, container_name)

@bot.tree.command(name="restart", description="Restarts your instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def restart(interaction: discord.Interaction, container_name: str):
    await restart_server(interaction, container_name)

@bot.tree.command(name="ping", description="Check the bot's latency.")
async def ping(interaction: discord.Interaction):
    await interaction.response.defer()
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: {latency}ms",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="list", description="Lists all your Instances")
async def list_servers(interaction: discord.Interaction):
    await interaction.response.defer()
    userid = str(interaction.user.id)
    servers = get_user_servers(userid)
    if servers:
        embed = discord.Embed(title="Your Instances", color=0x00ff00)
        for server in servers:
            _, container_name, _ = server.split('|')
            embed.add_field(name=container_name, value="32GB RAM - Premuim - 4 cores", inline=False)
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(embed=discord.Embed(description="You have no servers.", color=0xff0000))

async def execute_command(command):
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode(), stderr.decode()

PUBLIC_IP = '138.68.79.95'

async def capture_output(process, keyword):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        output = output.decode('utf-8').strip()
        if keyword in output:
            return output
    return None

@bot.tree.command(name="port-add", description="Adds a port forwarding rule")
@app_commands.describe(container_name="The name of the container", container_port="The port in the container")
async def port_add(interaction: discord.Interaction, container_name: str, container_port: int):
#    await interaction.response.defer()
    await interaction.response.send_message(embed=discord.Embed(description="### Setting up port forwarding. This might take a moment...", color=0x00ff00))

    public_port = generate_random_port()

    # Set up port forwarding inside the container
    command = f"ssh -o StrictHostKeyChecking=no -R {public_port}:localhost:{container_port} serveo.net -N -f"

    try:
        # Run the command in the background using Docker exec
        await asyncio.create_subprocess_exec(
            "docker", "exec", container_name, "bash", "-c", command,
            stdout=asyncio.subprocess.DEVNULL,  # No need to capture output
            stderr=asyncio.subprocess.DEVNULL  # No need to capture errors
        )

        # Respond immediately with the port and public IP
        await interaction.followup.send(embed=discord.Embed(description=f"### Port added successfully. Your service is hosted on {PUBLIC_IP}:{public_port}.", color=0x00ff00))

    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(description=f"### An unexpected error occurred: {e}", color=0xff0000))

@bot.tree.command(name="port-http", description="Forward HTTP traffic to your container")
@app_commands.describe(container_name="The name of your container", container_port="The port inside the container to forward")
async def port_forward_website(interaction: discord.Interaction, container_name: str, container_port: int):
 #   await interaction.response.defer()
    try:
        exec_cmd = await asyncio.create_subprocess_exec(
            "docker", "exec", container_name, "ssh", "-o StrictHostKeyChecking=no", "-R", f"80:localhost:{container_port}", "serveo.net",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        url_line = await capture_output(exec_cmd, "Forwarding HTTP traffic from")
        if url_line:
            url = url_line.split(" ")[-1]
            await interaction.response.send_message(embed=discord.Embed(description=f"### Website forwarded successfully. Your website is accessible at {url}.", color=0x00ff00))
        else:
            await interaction.response.send_message(embed=discord.Embed(description="### Failed to capture forwarding URL.", color=0xff0000))
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"### Error executing website forwarding: {e}", color=0xff0000))

@bot.tree.command(name="remove", description="Removes an Instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def remove_server(interaction: discord.Interaction, container_name: str):
    await interaction.response.defer()
    userid = str(interaction.user.id)
    container_id = get_container_id_from_database(userid, container_name)

    if not container_id:
        await interaction.response.send_message(embed=discord.Embed(description="### No Instance found for your user with that name.", color=0xff0000))
        return

    try:
        subprocess.run(["docker", "stop", container_id], check=True)
        subprocess.run(["docker", "rm", container_id], check=True)

        remove_from_database(container_id)

        await interaction.response.send_message(embed=discord.Embed(description=f"Instance '{container_name}' removed successfully.", color=0x00ff00))
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"Error removing instance: {e}", color=0xff0000))


@bot.tree.command(name="help", description="Shows the help message")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="help", color=0x00ff00)
    embed.add_field(name="/deploy", value="Creates a new Instance with Ubuntu 22.04.", inline=False)
    embed.add_field(name="/remove <ssh_command/Name>", value="Removes a server", inline=False)
    embed.add_field(name="/start <ssh_command/Name>", value="Start a server.", inline=False)
    embed.add_field(name="/stop <ssh_command/Name>", value="Stop a server.", inline=False)
    embed.add_field(name="/regen-ssh <ssh_command/Name>", value="Regenerates SSH cred", inline=False)
    embed.add_field(name="/restart <ssh_command/Name>", value="Stop a server.", inline=False)
    embed.add_field(name="/list", value="List all your servers", inline=False)
    embed.add_field(name="/ping", value="Check the bot's latency.", inline=False)
    embed.add_field(name="/node", value="Check The Node Storage Usage.", inline=False)
    embed.add_field(name="/bal", value="Check Your Balance.", inline=False)
    embed.add_field(name="/renew", value="Renew The VPS.", inline=False)
    embed.add_field(name="/earncredit", value="earn the credit.", inline=False)
    await interaction.response.send_message(embed=embed)


# run the bot
bot.run(TOKEN)
