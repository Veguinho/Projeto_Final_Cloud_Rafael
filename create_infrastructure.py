import boto3
from botocore.exceptions import ClientError
import time, paramiko, subprocess, os, stat 
from collections import defaultdict

#Deleta ips antigos e aloca ips novos para N. Virginia
ec2 = boto3.client('ec2', region_name='us-east-1')

filters = [{'Name': 'domain', 'Values': ['vpc']}]
response_associations_antigos = ec2.describe_addresses(Filters=filters)
try:
    if len(response_associations_antigos['Addresses']) > 0:
        response = ec2.release_address(AllocationId=response_associations_antigos['Addresses'][0]['AllocationId'])
        print('Old Address released')
except ClientError as e:
    print(e)

allocation_intermediario = ec2.allocate_address(Domain='vpc')
ip_do_webserver_intermediario = allocation_intermediario['PublicIp']

#Deleta LoadBalancer caso ja exista um
ec2_lb = boto3.client('elb')
try:
    lb_response = ec2_lb.describe_load_balancers(LoadBalancerNames=['LBProjetoFinalRafael'])
    if len(lb_response['LoadBalancerDescriptions']) > 0:
        ec2_lb.delete_load_balancer(LoadBalancerName='LBProjetoFinalRafael')
        print("LBProjetoFinalRafael already exists! Deleting loadbalancer LBProjetoFinalRafael...")
except Exception as E:
    print(E)

#############################################################################
######                 CRIAÇÃO DO DATABASE - MONGODB                 ########
#############################################################################

ec2 = boto3.client('ec2', region_name='us-east-2')

#Deleta ips antigos e aloca ips novos para OHIO
filters = [{'Name': 'domain', 'Values': ['vpc']}]
response_associations_antigos = ec2.describe_addresses(Filters=filters)
try:
    if len(response_associations_antigos['Addresses']) > 0:
        response = ec2.release_address(AllocationId=response_associations_antigos['Addresses'][0]['AllocationId'])
        print('Old Address released')
        if len(response_associations_antigos['Addresses']) > 1:
            response = ec2.release_address(AllocationId=response_associations_antigos['Addresses'][1]['AllocationId'])
            print('Old Address released')
except ClientError as e:
    print(e)
    
allocation_mongo = ec2.allocate_address(Domain='vpc')
ip_do_mongo = allocation_mongo['PublicIp']

allocation_flask = ec2.allocate_address(Domain='vpc')
ip_do_webserver_ohio = allocation_flask['PublicIp']


response_get = ec2.describe_key_pairs()
nome_chave = 'Projeto_Final_Rafael_MONGO'

#Cria key se nao existir
for key in response_get['KeyPairs']:
    if key['KeyName'] == nome_chave:
        print("Key Pair already exists!")
        response_delete = ec2.delete_key_pair(KeyName=nome_chave)
        print("Key Pair deleted!")
        #print(response_delete)

response_create = ec2.create_key_pair(KeyName=nome_chave)

#Cria chave e deleta se ja existir e faz chmod +x
if os.path.isfile(nome_chave + '.pem'):
    os.remove(nome_chave + '.pem')
outfile = open(nome_chave + '.pem','w')
KeyPairOut = str(response_create['KeyMaterial'])
outfile.write(KeyPairOut)
os.chmod(nome_chave + '.pem', 0o400)

#Cria security group DO MONGO e deleta caso ja exista um
response_sg = ec2.describe_vpcs()
vpc_id = response_sg.get('Vpcs', [{}])[0].get('VpcId', '')

waiter = ec2.get_waiter('instance_terminated')

#Deleta instancia se tiver o security group MONGODB
try:
    response = ec2.describe_instances()
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            #print("Instance: " + instance['InstanceId'])
            for securityGroup in instance['SecurityGroups']:
                #print("SG ID: {}, Name: {}".format(securityGroup['GroupId'], securityGroup['GroupName']))
                if securityGroup['GroupName'] == 'MONGODB':
                    print("Found instance in security group MONGODB. Deleting instance...")
                    ec2.terminate_instances(InstanceIds=[instance['InstanceId']])
                    waiter.wait(InstanceIds=[instance['InstanceId']])
except Exception as E:
    print(E)

try:
    response_sg = ec2.create_security_group(GroupName='MONGODB',
                                         Description='Security group do MongoDB',
                                         VpcId=vpc_id)
    security_group_id = response_sg['GroupId']
    print('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))

    data = ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {'IpProtocol': 'tcp',
             'FromPort': 5000,
             'ToPort': 5000,
             'IpRanges': [{'CidrIp': str(ip_do_webserver_ohio)+'/32'}]},
            {'IpProtocol': 'tcp',
             'FromPort': 22,
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
             {'IpProtocol': 'tcp',
             'FromPort': 27017,
             'ToPort': 27017,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])
    print('Ingress Successfully Set %s' % data)
except ClientError as e:
    print(e)
    print("Deleting Security Group and trying again...")
    response_sg_delete = ec2.delete_security_group(GroupName='MONGODB')
    response_sg = ec2.create_security_group(GroupName='MONGODB',
                                         Description='Security group do MongoDB',
                                         VpcId=vpc_id)
    security_group_id = response_sg['GroupId']
    print('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))

    data = ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {'IpProtocol': 'tcp',
             'FromPort': 5000,
             'ToPort': 5000,
             'IpRanges': [{'CidrIp': str(ip_do_webserver_ohio)+'/32'}]},
            {'IpProtocol': 'tcp',
             'FromPort': 22,
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
             {'IpProtocol': 'tcp',
             'FromPort': 27017,
             'ToPort': 27017,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])
    print('Ingress Successfully Set %s' % data)

user_data_mongo = '''#!/bin/bash
sudo su
git clone https://github.com/Veguinho/Projeto_Final_Cloud.git
cd /Projeto_Final_Cloud
chmod +x webserver_MONGODB.sh
./webserver_MONGODB.sh
pip3 install pymongo
python3 create_mongo_database.py'''

ec2_create = boto3.resource('ec2', region_name='us-east-2')
try: 
    print("Starting t2.micro instance...")
    response_instance = ec2_create.create_instances(ImageId='ami-be7753db',
                                MinCount=1,
                                MaxCount=1,
                                KeyName=nome_chave,
                                InstanceType='t2.micro',
                                SecurityGroups=['MONGODB'],
                                TagSpecifications=[{'ResourceType': 'instance' ,'Tags': [{'Key': 'Owner','Value': 'Rafael'}]}],
                                UserData=user_data_mongo)
except ClientError as e:
    print(e)

waiter = ec2.get_waiter('instance_running')


#ALOCA IP ESTATICO PARA A INSTANCIA
try:
    response = ec2.describe_instances()
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            for securityGroup in instance['SecurityGroups']:
                if securityGroup['GroupName'] == 'MONGODB':
                    print("Waiting for instance to become ready...")
                    waiter.wait(InstanceIds=[instance['InstanceId']])
                    response_allocation = ec2.associate_address(AllocationId=allocation_mongo['AllocationId'],InstanceId=instance['InstanceId'])
                    #print(response)
except ClientError as e:
    print(e)

#############################################################################
########                CRIAÇÃO DO WEBSERVER - FLASK                #########
#############################################################################
nome_chave = 'Projeto_Final_Rafael'

ec2 = boto3.client('ec2', region_name='us-east-2')
response_get = ec2.describe_key_pairs()

#Cria key se nao existir
for key in response_get['KeyPairs']:
    if key['KeyName'] == nome_chave:
        print("Key Pair already exists!")
        response_delete = ec2.delete_key_pair(KeyName=nome_chave)
        print("Key Pair deleted!")
        #print(response_delete)

response_create = ec2.create_key_pair(KeyName=nome_chave)
print("Key Pair created!")

#Cria chave e deleta se ja existir e faz chmod +x
if os.path.isfile(nome_chave + '.pem'):
    os.remove(nome_chave + '.pem')
outfile = open(nome_chave + '.pem','w')
KeyPairOut = str(response_create['KeyMaterial'])
outfile.write(KeyPairOut)
os.chmod(nome_chave + '.pem', 0o400)

waiter = ec2.get_waiter('instance_terminated')

#Deleta instancia se tiver o security group APS3
try:
    response = ec2.describe_instances()
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            #print("Instance: " + instance['InstanceId'])
            for securityGroup in instance['SecurityGroups']:
                #print("SG ID: {}, Name: {}".format(securityGroup['GroupId'], securityGroup['GroupName']))
                if securityGroup['GroupName'] == 'APS3':
                    print("Found instance in security group APS3. Deleting instance...")
                    ec2.terminate_instances(InstanceIds=[instance['InstanceId']])
                    waiter.wait(InstanceIds=[instance['InstanceId']])

except Exception as E:
    print(E)

#Cria security group e deleta caso ja exista um
response_sg = ec2.describe_vpcs()
vpc_id = response_sg.get('Vpcs', [{}])[0].get('VpcId', '')

try:
    response_sg = ec2.create_security_group(GroupName='APS3',
                                         Description='Security group da aps3',
                                         VpcId=vpc_id)
    security_group_id = response_sg['GroupId']
    print('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))

    data = ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {'IpProtocol': 'tcp',
             'FromPort': 5000,
             'ToPort': 5000,
             'IpRanges': [{'CidrIp': str(ip_do_webserver_intermediario)+'/32'}]},
            {'IpProtocol': 'tcp',
             'FromPort': 22,
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
             {'IpProtocol': 'tcp',
             'FromPort': 27017,
             'ToPort': 27017,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])
    print('Ingress Successfully Set %s' % data)
except ClientError as e:
    print(e)
    print("Deleting Security Group and trying again...")
    response_sg_delete = ec2.delete_security_group(GroupName='APS3')
    response_sg = ec2.create_security_group(GroupName='APS3',
                                         Description='Security group da aps3',
                                         VpcId=vpc_id)
    security_group_id = response_sg['GroupId']
    print('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))

    data = ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {'IpProtocol': 'tcp',
             'FromPort': 5000,
             'ToPort': 5000,
             'IpRanges': [{'CidrIp': str(ip_do_webserver_intermediario)+'/32'}]},
            {'IpProtocol': 'tcp',
             'FromPort': 22,
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
             {'IpProtocol': 'tcp',
             'FromPort': 27017,
             'ToPort': 27017,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])
    print('Ingress Successfully Set %s' % data)

#print("VALOR DO IP DO MONGO: " + str(ip_do_mongo))
user_data = '''#!/bin/bash
sudo su
git clone https://github.com/Veguinho/Projeto_Final_Cloud.git
cd /Projeto_Final_Cloud
chmod +x webserver.sh
echo "export MONGODB_HOST={}" >> ~/.bashrc
export MONGODB_HOST={}
echo $MONGODB_HOST > address
./webserver.sh'''.format(str(ip_do_mongo), str(ip_do_mongo))

#Cria instancia
ec2_create = boto3.resource('ec2', region_name='us-east-2')
try: 
    print("Starting t2.micro instance...")
    response_instance = ec2_create.create_instances(ImageId='ami-be7753db',
                                MinCount=1,
                                MaxCount=1,
                                KeyName=nome_chave,
                                InstanceType='t2.micro',
                                SecurityGroups=['APS3'],
                                TagSpecifications=[{'ResourceType': 'instance' ,'Tags': [{'Key': 'Owner','Value': 'Rafael'}]}],
                                UserData=user_data)
except ClientError as e:
    print(e)

waiter = ec2.get_waiter('instance_running')

#ALOCA IP ESTATICO PARA A INSTANCIA
try:
    response = ec2.describe_instances()
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            for securityGroup in instance['SecurityGroups']:
                if securityGroup['GroupName'] == 'APS3':
                    print("Waiting for instance to become ready...")
                    waiter.wait(InstanceIds=[instance['InstanceId']])
                    response_allocation = ec2.associate_address(AllocationId=allocation_flask['AllocationId'],InstanceId=instance['InstanceId'])
                    print("WEBSERVER OHIO: " + str(ip_do_webserver_ohio))
                    #print(response)
except ClientError as e:
    print(e)

#############################################################################
########              CRIAÇÃO DO WEBSERVER INTERMEDIARIO            #########
#############################################################################

print("Creating webserver intermediario on North Virginia...")

nome_chave = 'Projeto_Final_Rafael_WBSI'

ec2 = boto3.client('ec2', region_name='us-east-1')
response_get = ec2.describe_key_pairs()

ec2_autoscaling = boto3.client('autoscaling', region_name='us-east-1')

#Cria key se nao existir
for key in response_get['KeyPairs']:
    if key['KeyName'] == nome_chave:
        print("Key Pair already exists!")
        response_delete = ec2.delete_key_pair(KeyName=nome_chave)
        print("Key Pair deleted!")
        #print(response_delete)

response_create = ec2.create_key_pair(KeyName=nome_chave)
print("Key Pair created!")

#Cria chave e deleta se ja existir e faz chmod +x
if os.path.isfile(nome_chave + '.pem'):
    os.remove(nome_chave + '.pem')
outfile = open(nome_chave + '.pem','w')
KeyPairOut = str(response_create['KeyMaterial'])
outfile.write(KeyPairOut)
os.chmod(nome_chave + '.pem', 0o400)

waiter = ec2.get_waiter('instance_terminated')

#Deleta instancia se tiver o security group Webserver_I
try:
    response = ec2.describe_instances()
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            #print("Instance: " + instance['InstanceId'])
            for securityGroup in instance['SecurityGroups']:
                #print("SG ID: {}, Name: {}".format(securityGroup['GroupId'], securityGroup['GroupName']))
                if securityGroup['GroupName'] == 'Webserver_I':
                    print("Found instance in security group Webserver_I. Deleting instance...")
                    ec2.terminate_instances(InstanceIds=[instance['InstanceId']])
                    waiter.wait(InstanceIds=[instance['InstanceId']])

except Exception as E:
    print("Deu erro!")
    print(E)

#Cria security group e deleta caso ja exista um
response_sg = ec2.describe_vpcs()
vpc_id = response_sg.get('Vpcs', [{}])[0].get('VpcId', '')

try:
    response_sg = ec2.create_security_group(GroupName='Webserver_I',
                                         Description='Security group do webserver intermediario',
                                         VpcId=vpc_id)
    security_group_id = response_sg['GroupId']
    print('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))

    data = ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {'IpProtocol': 'tcp',
             'FromPort': 5000,
             'ToPort': 5000,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
             'FromPort': 22,
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
             {'IpProtocol': 'tcp',
             'FromPort': 27017,
             'ToPort': 27017,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])
    print('Ingress Successfully Set %s' % data)
except ClientError as e:
    print(e)
    print("Deleting Security Group and trying again...")
    response_sg_delete = ec2.delete_security_group(GroupName='Webserver_I')
    response_sg = ec2.create_security_group(GroupName='Webserver_I',
                                         Description='Security group do webserver intermediario',
                                         VpcId=vpc_id)
    security_group_id = response_sg['GroupId']
    print('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))

    data = ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {'IpProtocol': 'tcp',
             'FromPort': 5000,
             'ToPort': 5000,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
             'FromPort': 22,
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
             {'IpProtocol': 'tcp',
             'FromPort': 27017,
             'ToPort': 27017,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])
    print('Ingress Successfully Set %s' % data)

#print("VALOR DO IP DO MONGO: " + str(ip_do_mongo))
user_data = '''#!/bin/bash
sudo su
git clone https://github.com/Veguinho/Projeto_Final_Cloud.git
cd /Projeto_Final_Cloud
chmod +x webserver_pass_on.sh
echo "export PASS_TO_HOST={}" >> ~/.bashrc
export PASS_TO_HOST={}
echo $PASS_TO_HOST > address
./webserver_pass_on.sh'''.format(str(ip_do_webserver_ohio), str(ip_do_webserver_ohio))

#Cria instancia
ec2_create = boto3.resource('ec2', region_name='us-east-1')
try: 
    print("Starting t2.micro instance...")
    response_instance = ec2_create.create_instances(ImageId='ami-02fb1c72d81ced91a',
                                MinCount=1,
                                MaxCount=1,
                                KeyName=nome_chave,
                                InstanceType='t2.micro',
                                SecurityGroups=['Webserver_I'],
                                TagSpecifications=[{'ResourceType': 'instance' ,'Tags': [{'Key': 'Owner','Value': 'Rafael'}]}],
                                UserData=user_data)
except ClientError as e:
    print(e)

waiter = ec2.get_waiter('instance_running')


#ALOCA IP ESTATICO PARA A INSTANCIA
try:
    response = ec2.describe_instances()
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            for securityGroup in instance['SecurityGroups']:
                if securityGroup['GroupName'] == 'Webserver_I':
                    print("Waiting for instance to become ready...")
                    waiter.wait(InstanceIds=[instance['InstanceId']])
                    response_allocation = ec2.associate_address(AllocationId=allocation_intermediario['AllocationId'],InstanceId=instance['InstanceId'])
                    print("WEBSERVER INTERMEDIARIO: " + str(ip_do_webserver_intermediario))
except ClientError as e:
    print("DEU ERRO!")
    print(e)

#############################################################################
########          CRIAÇÃO DO LOADBALANCER E AUTOSCALING GROUP       #########
#############################################################################

###
# Criando a instancia para fazer a imagem do LoadBalancer e launch configuration#
###
print("Creating new LoadBalancer on North Virginia...")

nome_chave = 'Projeto_Final_Rafael_LB'

ec2 = boto3.client('ec2', region_name='us-east-1')
response_get = ec2.describe_key_pairs()

ec2_autoscaling = boto3.client('autoscaling', region_name='us-east-1')

#Delete Autoscaling if exists
as_response = ec2_autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=['ASProjetoFinal_Rafael'])
if len(as_response['AutoScalingGroups']) > 0:
    ec2_autoscaling.delete_auto_scaling_group(AutoScalingGroupName='ASProjetoFinal_Rafael', ForceDelete=True)
    print("ASProjetoFinal_Rafael already exists! Deleting auto scaling group ASProjetoFinal_Rafael...")

#Cria key se nao existir
for key in response_get['KeyPairs']:
    if key['KeyName'] == nome_chave:
        print("Key Pair already exists!")
        response_delete = ec2.delete_key_pair(KeyName=nome_chave)
        print("Key Pair deleted!")
        #print(response_delete)

response_create = ec2.create_key_pair(KeyName=nome_chave)
print("Key Pair created!")

#Cria chave e deleta se ja existir e faz chmod +x
if os.path.isfile(nome_chave + '.pem'):
    os.remove(nome_chave + '.pem')
outfile = open(nome_chave + '.pem','w')
KeyPairOut = str(response_create['KeyMaterial'])
outfile.write(KeyPairOut)
os.chmod(nome_chave + '.pem', 0o400)

waiter = ec2.get_waiter('instance_terminated')

#Deleta instancia se tiver o security group LoadBalancer
try:
    response = ec2.describe_instances()
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            #print("Instance: " + instance['InstanceId'])
            for securityGroup in instance['SecurityGroups']:
                #print("SG ID: {}, Name: {}".format(securityGroup['GroupId'], securityGroup['GroupName']))
                if securityGroup['GroupName'] == 'LoadBalancer':
                    print("Found instance in security group LoadBalancer. Deleting instance...")
                    ec2.terminate_instances(InstanceIds=[instance['InstanceId']])
                    waiter.wait(InstanceIds=[instance['InstanceId']])

except Exception as E:
    print(E)



#Cria security group e deleta caso ja exista um
response_sg = ec2.describe_vpcs()
vpc_id = response_sg.get('Vpcs', [{}])[0].get('VpcId', '')

try:
    response_sg = ec2.create_security_group(GroupName='LoadBalancer',
                                         Description='Security group do loadbalancer',
                                         VpcId=vpc_id)
    security_group_id = response_sg['GroupId']
    print('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))

    data = ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {'IpProtocol': 'tcp',
             'FromPort': 5000,
             'ToPort': 5000,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
             'FromPort': 22,
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
             {'IpProtocol': 'tcp',
             'FromPort': 27017,
             'ToPort': 27017,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])
    print('Ingress Successfully Set %s' % data)
except ClientError as e:
    print(e)
    print("Deleting Security Group and trying again...")
    response_sg_delete = ec2.delete_security_group(GroupName='LoadBalancer')
    response_sg = ec2.create_security_group(GroupName='LoadBalancer',
                                         Description='Security group do loadbalancer',
                                         VpcId=vpc_id)
    security_group_id = response_sg['GroupId']
    print('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))

    data = ec2.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {'IpProtocol': 'tcp',
             'FromPort': 5000,
             'ToPort': 5000,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
             'FromPort': 22,
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
             {'IpProtocol': 'tcp',
             'FromPort': 27017,
             'ToPort': 27017,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])
    print('Ingress Successfully Set %s' % data)

#print("VALOR DO IP DO MONGO: " + str(ip_do_mongo))
user_data = '''#!/bin/bash
sudo su
git clone https://github.com/Veguinho/Projeto_Final_Cloud.git
cd /Projeto_Final_Cloud
chmod +x webserver_pass_on.sh
echo "export PASS_TO_HOST={}" >> ~/.bashrc
export PASS_TO_HOST={}
echo $PASS_TO_HOST > address
./webserver_pass_on.sh'''.format(str(ip_do_webserver_intermediario), str(ip_do_webserver_intermediario))

#Cria instancia
ec2_create = boto3.resource('ec2', region_name='us-east-1')
try: 
    print("Starting t2.micro instance...")
    response_instance = ec2_create.create_instances(ImageId='ami-02fb1c72d81ced91a',
                                MinCount=1,
                                MaxCount=1,
                                KeyName=nome_chave,
                                InstanceType='t2.micro',
                                SecurityGroups=['LoadBalancer'],
                                TagSpecifications=[{'ResourceType': 'instance' ,'Tags': [{'Key': 'Owner','Value': 'Rafael'}]}],
                                UserData=user_data)
except ClientError as e:
    print(e)

ec2 = boto3.client('ec2', region_name='us-east-1')

waiter = ec2.get_waiter('instance_running')

images_response = ec2.describe_images(Filters=[{'Name':'name', 'Values':['imagem_lb']}])
if len(images_response['Images']) > 0:
    ec2.deregister_image(ImageId=images_response['Images'][0]['ImageId'])
    print("Deleting image imagem_lb...")

#Cria AMI da instancia
try:
    response = ec2.describe_instances()
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            #print("Instance: " + instance['InstanceId'])
            for securityGroup in instance['SecurityGroups']:
                #print("SG ID: {}, Name: {}".format(securityGroup['GroupId'], securityGroup['GroupName']))
                if securityGroup['GroupName'] == 'LoadBalancer':
                    print("Waiting for instance to become ready...")
                    waiter.wait(InstanceIds=[instance['InstanceId']])
                    print("Creating image imagem_lb...")
                    image_created = ec2.create_image(InstanceId=instance['InstanceId'], NoReboot=True, Name="imagem_lb")
                    print("Found instance in security group Loadbalancer. Creating AMI and deleting instance...")
                    ec2.terminate_instances(InstanceIds=[instance['InstanceId']])
                    print("Deleting AMI instance creator...")

except Exception as E:
    print(E)

#Cria launch configuration
lc_response = ec2_autoscaling.describe_launch_configurations(LaunchConfigurationNames=['Launch_config_Rafael'])
if len(lc_response['LaunchConfigurations']) > 0:
    ec2_autoscaling.delete_launch_configuration(LaunchConfigurationName='Launch_config_Rafael')
    print("Launch_config_Rafael already exists! Deleting launch configuration Launch_config_Rafael...")

print("Creating Launch Configuration: Launch_config_Rafael")
ec2_autoscaling.create_launch_configuration(LaunchConfigurationName='Launch_config_Rafael',
                                            ImageId=image_created['ImageId'], 
                                            SecurityGroups=['LoadBalancer'],
                                            InstanceType='t2.micro',
                                            KeyName=nome_chave,
                                            UserData=user_data)

try:
    security_group_lb = ec2.describe_security_groups(GroupNames=['LoadBalancer'])
except ClientError as e:
    print(e)

print("Creating loadbalancer: LBProjetoFinalRafael")
ec2_lb.create_load_balancer(LoadBalancerName='LBProjetoFinalRafael', Listeners=[{'Protocol': 'tcp',
                                                                                 'LoadBalancerPort': 5000,
                                                                                 'InstanceProtocol': 'tcp',
                                                                                 'InstancePort': 5000}], 
                                                                       AvailabilityZones=['us-east-1a','us-east-1b','us-east-1c','us-east-1d','us-east-1e','us-east-1f'],
                                                                       SecurityGroups=[security_group_lb['SecurityGroups'][0]['GroupId']])

#Cria autoscaling group
print("Creating auto scaling group: ASProjetoFinal_Rafael")
ec2_autoscaling.create_auto_scaling_group(AutoScalingGroupName='ASProjetoFinal_Rafael', 
                                            LaunchConfigurationName='Launch_config_Rafael', 
                                            LoadBalancerNames=['LBProjetoFinalRafael'], 
                                            MinSize=1, 
                                            MaxSize=3,
                                            AvailabilityZones=['us-east-1a','us-east-1b','us-east-1c','us-east-1d','us-east-1e','us-east-1f'])


