
data "aws_iam_policy_document" "sqs_policy" {

  statement {

    actions = [
      "sqs:SendMessage",
    ]

    resources = ["*"]

    principals {
      type = "Service"
      identifiers = [
        "s3.amazonaws.com",
      ]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [module.param_requests_bucket.arn]
    }
  }
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${local.prefix}-review-dlq"
  tags                      = var.common_tags
  message_retention_seconds = 1209600 # 2 weeks
  kms_master_key_id         = var.kms_key_id
}

resource "aws_sqs_queue" "review" {
  name                      = "${local.prefix}-review"
  tags                      = var.common_tags
  policy                    = data.aws_iam_policy_document.sqs_policy.json
  message_retention_seconds = 1209600 # 2 week

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })

  kms_master_key_id = var.kms_key_id
}
