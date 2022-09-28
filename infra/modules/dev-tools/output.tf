output "param_requests_s3_bucket" {
  value = module.param_requests_bucket.bucket
}

output "param_requests_s3_bucket_arn" {
  value = module.param_requests_bucket.arn
}

output "main_queue_arn" {
  value = aws_sqs_queue.review.arn
}
