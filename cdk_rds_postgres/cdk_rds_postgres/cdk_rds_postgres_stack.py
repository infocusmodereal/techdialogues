import json

from aws_cdk import (
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_secretsmanager as secretsmanager,
    aws_iam as iam,
    core as cdk,
)

from constructs import Construct

class CdkRdsPostgresStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        
        vpc_ifm = ec2.Vpc(
            self,
            "vpc_ifm",
            max_azs=3,
            cidr="10.5.0.0/22",
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC,
                    name="Public",
                    cidr_mask=26
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE,
                    name="Private",
                    cidr_mask=26
                ),
            ],
            nat_gateways=3,
        )

        subnet_group_ifm = rds.SubnetGroup(
            self,
            "subnet_group_ifm",
            vpc=vpc_ifm,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT
            ),
            subnet_group_name="ifm-postgres-subnet-group",
            description="Subnet group for ifm postgres",
        )

        security_group_ifm_db = ec2.SecurityGroup(
            self,
            "security_group_ifm_db",
            vpc=vpc_ifm,
            security_group_name="security_group_ifm_db",
            allow_all_outbound=True,
        )

        security_group_ifm_db.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc_ifm.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
        )

        secret_db_creds = secretsmanager.Secret(
            self,
            "secret_db_creds",
            secret_name=f"ifm/db_creds",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps({"username": "ifm"}),
                exclude_punctuation=True,
                generate_string_key="password",
            ),
        )
        
        role_enhanced_monitoring = iam.Role(
            self,
            "role_enhanced_monitoring",
            assumed_by=iam.ServicePrincipal("monitoring.rds.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonRDSEnhancedMonitoringRole"
                ),
            ],
            role_name="rds_enhanced_monitoring",
        )
        
        parameter_group_postgres = rds.ParameterGroup(
            self,
            "parameter_group_postgres",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_14
            ),
            parameters={
                "max_standby_streaming_delay": "600000",  # milliseconds (5 minutes)
                "max_standby_archive_delay": "600000",  # milliseconds (5 minutes)
                "rds.logical_replication": "1",  # 1 means replication is enabled
            },
        )
        
        self.rds_db_postgres = rds.DatabaseInstance(
            self,
            "rds_db_postgres",
            instance_identifier="ifm-postgres",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_14
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.M6G, ec2.InstanceSize.LARGE
            ),
            parameter_group=parameter_group_postgres,
            allocated_storage=200,
            max_allocated_storage=500,
            credentials=rds.Credentials.from_secret(secret_db_creds),
            database_name="ifmdb",
            vpc=vpc_ifm,
            subnet_group=subnet_group_ifm,
            enable_performance_insights=True,
            performance_insight_retention=rds.PerformanceInsightRetention.DEFAULT,
            monitoring_interval=cdk.Duration.seconds(60),
            publicly_accessible=False,
            monitoring_role=role_enhanced_monitoring,
            backup_retention=cdk.Duration.days(7),
            security_groups=[
                security_group_ifm_db,
            ],
        )

        self.rds_db_postgres_replica_1 = rds.DatabaseInstanceReadReplica(
            self,
            "rds_db_postgres_replica_1",
            instance_identifier="ifm-postgres-replica-1",
            source_database_instance=self.rds_db_postgres,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.M6G, ec2.InstanceSize.XLARGE
            ),
            vpc=vpc_ifm,
            security_groups=[security_group_ifm_db],
            subnet_group=subnet_group_ifm,
        )

        self.rds_db_postgres_replica_2 = rds.DatabaseInstanceReadReplica(
            self,
            "rds_db_postgres_replica_2",
            instance_identifier="ifm-postgres-replica-2",
            source_database_instance=self.rds_db_postgres,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.M6G, ec2.InstanceSize.XLARGE
            ),
            vpc=vpc_ifm,
            security_groups=[security_group_ifm_db],
            subnet_group=subnet_group_ifm,
        )