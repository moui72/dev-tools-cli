resource "aws_iam_role" "dev_tools_lambda_iam_role" {
  name = "${var.prefix}-dev-tools-lambda"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": "LambdaAssumeRole"
    }
  ]
}
EOF
}

data "aws_iam_policy_document" "policy" {
  statement {
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["arn:aws:logs:*:*:*"]

    sid = "Logs"
  }


  statement {
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:PutObjectAcl",
      "s3:DeleteObject",
    ]

    resources = [
      module.param_requests_bucket.arn,
      "${module.param_requests_bucket.arn}/*",
    ]

    sid = "DevToolsS3"
  }


  statement {
    effect = "Allow"

    actions = [
      "sqs:ReceiveMessage",
      "sqs:SendMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ChangeMessageVisibility",
    ]

    resources = [
      module.processor.processor_queue_arn,
    ]
    sid = "DevToolsSQSFor${var.common_tags["env"]}"
  }

  statement {
    effect = "Allow"

    actions = [
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:Encrypt",
      "kms:DescribeKey",
      "kms:Decrypt"
    ]

    resources = [var.kms_arn]
    sid       = "standardKMS"
  }

  statement {
    actions = [
      "ssm:Get*",
      "ssm:PutParameter",
    ]

    resources = [
      "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:parameter/${var.common_tags["env"]}/*",
    ]
    sid = "DevToolsParamStore"
  }
}

resource "aws_iam_policy" "lambda_policy" {
  path   = "/"
  policy = data.aws_iam_policy_document.policy.json
}

resource "aws_iam_role_policy_attachment" "dev_tools_lambda" {
  role       = aws_iam_role.dev_tools_lambda_iam_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}
