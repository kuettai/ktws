// 4. Stock transfers: a manager may only send stock FROM their own branch. HQ may move any stock.
forbid(principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"OpsApi___requestStockTransfer",
  resource == AgentCore::Gateway::"<GATEWAY_ARN>")
unless { (principal.hasTag("role") && principal.getTag("role") == "hq") ||
         (principal.hasTag("role") && principal.getTag("role") == "manager" &&
          principal.hasTag("branch_id") && context.input.fromBranchId == principal.getTag("branch_id")) };
