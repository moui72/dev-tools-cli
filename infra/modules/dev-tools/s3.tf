module "param_requests_bucket" {
  # private module: creates bucket and access controls
  source        = "../../s3"
  name          = "${local.prefix}-param-requests"
  tags          = local.common_tags
  attach_policy = false
  acl           = "private"
  sse_algorithm = "AES256"
  force_destroy = true
  notification_queues = [
    {
      arn           = module.processor.processor_queue_arn
      events        = ["s3:ObjectCreated:*"]
      filter_prefix = "requested/"
      filter_suffix = ".json"
    },
    {
      arn           = module.processor.processor_queue_arn
      events        = ["s3:ObjectCreated:*"]
      filter_prefix = "approved/"
      filter_suffix = ".json"
    },
    {
      arn           = module.processor.processor_queue_arn
      events        = ["s3:ObjectCreated:*"]
      filter_prefix = "rejected/"
      filter_suffix = ".json"
    },
    {
      arn           = aws_sqs_queue.review.arn
      events        = ["s3:ObjectCreated:*"]
      filter_prefix = "review/"
      filter_suffix = ".json"
    }
  ]
  lifecycle_rules = [
    {
      id            = "rejected"
      enabled       = true
      filter_prefix = "rejected/"

      transition = [{
        days          = 3
        storage_class = "DEEP_ARCHIVE"
      }]
    },
    {
      id            = "accepted"
      enabled       = true
      filter_prefix = "accepted/"

      transition = [{
        days          = 3
        storage_class = "DEEP_ARCHIVE"
      }]
    },
  ]
}


module "packages_bucket" {
  # private module: creates bucket and access controls
  source        = "../../s3"
  name          = "${local.prefix}-packages"
  tags          = local.common_tags
  attach_policy = false
  acl           = "private"
  sse_algorithm = "AES256"
  force_destroy = true
}

data "archive_file" "package" {
  type             = "zip"
  source_dir       = "${path.module}/packages/handler/"
  output_file_mode = "0666"
  output_path      = "${path.module}/packages/handler.zip"
}

resource "aws_s3_object" "package" {
  bucket = module.packages_bucket.bucket
  key    = "handler.zip"
  source = data.archive_file.package.output_path
  etag   = filemd5(data.archive_file.package.output_path)
}
