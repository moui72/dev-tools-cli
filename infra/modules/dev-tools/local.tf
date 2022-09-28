locals {
  prefix      = "${var.prefix}-dev-tools"
  common_tags = merge(var.common_tags, var.tags)
}
