// 3. Refunds change data: only managers (and HQ) may issue them, through either target.
forbid(principal is AgentCore::OAuthUser,
  action in [AgentCore::Action::"OpsApi___issueRefund", AgentCore::Action::"RstMcp___issue_refund"],
  resource == AgentCore::Gateway::"<GATEWAY_ARN>")
unless { principal.hasTag("role") && (principal.getTag("role") == "manager" || principal.getTag("role") == "hq") };
