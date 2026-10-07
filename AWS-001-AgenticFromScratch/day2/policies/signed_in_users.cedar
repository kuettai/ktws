// 1. Start from "allowed": anyone signed in through Cognito with a role may call the tools.
//    The rules below take things away (in Cedar, a forbid always wins over a permit).
permit(principal is AgentCore::OAuthUser, action, resource is AgentCore::Gateway)
when { principal.hasTag("role") };
