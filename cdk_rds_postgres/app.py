#!/usr/bin/env python3
import os

import aws_cdk.core as cdk

from cdk_rds_postgres.cdk_rds_postgres_stack import CdkRdsPostgresStack


app = cdk.App()
CdkRdsPostgresStack(
    app, 
    "CdkRdsPostgresStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), 
        region=os.getenv("CDK_DEFAULT_REGION")
    ),
)

app.synth()
