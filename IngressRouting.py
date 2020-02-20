
import boto3
from time import sleep

ec2 = boto3.resource('ec2')
ec2client = boto3.client('ec2')

#The following block will create VPC with the CIDR 10.0.0.0/16 you can change it as per your wish

vpc = ec2.create_vpc(CidrBlock='10.0.0.0/16')
vpc.wait_until_available()

#Creates Internet gateway and attaches to VPC
IGW = ec2.create_internet_gateway()
vpc.attach_internet_gateway(InternetGatewayId=IGW.id)

#subnet's creation and route table association

PUBsubnet =ec2.create_subnet(CidrBlock='10.0.0.0/24', VpcId=vpc.id)
PRIVsubnet=ec2.create_subnet(CidrBlock='10.0.1.0/24', VpcId=vpc.id)

PUBroutetable = vpc.create_route_table()
PUBroutetable.associate_with_subnet(SubnetId=PUBsubnet.id)
route1 = PUBroutetable.create_route(DestinationCidrBlock='0.0.0.0/0', GatewayId=IGW.id)

PRIVroutetable = vpc.create_route_table()
PRIVroutetable.associate_with_subnet(SubnetId=PRIVsubnet.id)

#Edge association of the IGW to the route table for enabling VPC Ingress routing
GWroutetable = vpc.create_route_table()
test = ec2client.associate_route_table(RouteTableId=GWroutetable.id, GatewayId=IGW.id)

#Create Security group to allow ssh and HTTPS access to the PA firewall
SG = ec2.create_security_group(GroupName='FW', Description='Allow HTTPS and SSH', VpcId=vpc.id)
SG.authorize_ingress(CidrIp='0.0.0.0/0', IpProtocol='tcp', FromPort=22, ToPort=22)
SG.authorize_ingress(CidrIp='0.0.0.0/0', IpProtocol='tcp', FromPort=443, ToPort=443)

firewall = ec2.create_instances(
    ImageId='ami-09229138a623c0ecf',
    MinCount=1,
    MaxCount=1,
    InstanceType='c3.2xlarge',
    KeyName='YourKey',
    SubnetId=PUBsubnet.id
)

response = firewall[0].modify_attribute(Groups=[SG.id])

temp = firewall[0]

print(temp.id)

#create and attach dataplane ENI to PA firewall

network_interface = ec2.create_network_interface(SubnetId=PUBsubnet.id)
print(network_interface.id)
type(network_interface.id)

sleep(120)

eniattach = ec2client.attach_network_interface(DeviceIndex=1, NetworkInterfaceId=str(network_interface.id), InstanceId=str(temp.id))

#Add the route to point the Ingress and Egress traffic to PA fiewall
route2 =PRIVroutetable.create_route(DestinationCidrBlock='0.0.0.0/0', NetworkInterfaceId=str(network_interface.id))
print(route2)
route3 = ec2.Route(GWroutetable.id, '10.0.0.0/16')
route3.replace(NetworkInterfaceId=str(network_interface.id))

# Allocate an elastic IP to management interface
eip2 = ec2client.allocate_address(Domain='vpc')
# Associate the elastic IP address with the instance launched above
ec2client.associate_address(
     InstanceId=temp.id,
     AllocationId=eip2["AllocationId"])

# Allocate an elastic IP
eip = ec2client.allocate_address(Domain='vpc')
# Associate the elastic IP address with the instance launched above
ec2client.associate_address(
     NetworkInterfaceId=network_interface.id,
     AllocationId=eip["AllocationId"])

print('Finished!')
