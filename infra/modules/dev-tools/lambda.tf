module "processor" {
  # private module: creates lambda, SQS queue, S3 events to SQS mappingm etc.
  source               = "../eventing/lambda-processor"
  name                 = "request-processor"
  common_tags          = local.common_tags
  tags                 = {}
  prefix               = local.prefix
  lambda_handler       = "handler.handle"
  role_arn             = aws_iam_role.dev_tools_lambda_iam_role.arn
  security_group_ids   = var.security_group_ids
  subnet_ids           = var.private_subnet_ids
  s3_event_source_arns = [module.param_requests_bucket.arn]
  kms_key_id           = var.kms_key_id

  function_source_s3_bucket = module.packages_bucket.bucket
  function_source_s3_key    = aws_s3_object.package.key
  source_code_hash          = aws_s3_object.package.etag
  lambda_runtime            = "python3.9"

  lambda_env_vars = {
    SLACK_NOTIFICATION_CHANNEL = var.slack_channel
  }
}
