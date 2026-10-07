// 2. Live data and refunds: managers and staff only for their own branch. HQ: any branch.
//    context.input holds the tool's arguments; the principal's tags are the token's claims (text).
forbid(principal is AgentCore::OAuthUser,
  action in [AgentCore::Action::"OpsApi___getStockLevels", AgentCore::Action::"OpsApi___getItemStock", AgentCore::Action::"OpsApi___getTodaySales",
             AgentCore::Action::"OpsApi___listOrders", AgentCore::Action::"OpsApi___getOrder", AgentCore::Action::"OpsApi___issueRefund"],
  resource == AgentCore::Gateway::"<GATEWAY_ARN>")
unless { (principal.hasTag("role") && principal.getTag("role") == "hq") ||
         (principal.hasTag("branch_id") && context.input.branchId == principal.getTag("branch_id")) };
