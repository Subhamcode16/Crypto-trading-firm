import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  signals: defineTable({
    signalId: v.string(),
    timestamp: v.string(),
    tokenAddress: v.string(),
    tokenName: v.string(),
    tokenSymbol: v.string(),
    entryPrice: v.float64(),
    positionSizeUsd: v.float64(),
    confidenceScore: v.float64(),
    reason: v.string(),
    status: v.string(),
    telegramSent: v.boolean(),
  }).index("by_tokenAndTimestamp", ["tokenAddress", "timestamp"]),

  trades: defineTable({
    tradeId: v.string(),
    userId: v.string(), // Added for user filtering
    signalId: v.string(),
    tokenAddress: v.string(),
    entryPrice: v.float64(),
    entryTime: v.string(),
    entryTxHash: v.string(),
    positionSizeUsd: v.float64(),
    status: v.string(),
    stopLossPrice: v.float64(),
    tp1Price: v.float64(),
    tp2Price: v.float64(),
    totalProfitUsd: v.optional(v.float64()),
    totalProfitPct: v.optional(v.float64()),
    exitTime: v.optional(v.string()),
    exitTxHash: v.optional(v.string()),
  })
    .index("by_status", ["status"])
    .index("by_user", ["userId"]), // Added index for user queries

  daily_stats: defineTable({
    userId: v.string(),
    date: v.string(), // ISO date YYYY-MM-DD
    realizedPnlUsd: v.float64(),
    realizedLossUsd: v.float64(),
    dailyLossLimitUsd: v.float64(),
    updatedAt: v.string(),
  }).index("by_user_date", ["userId", "date"]),

  agent_intel: defineTable({
    tokenAddress: v.string(),
    agentType: v.string(), // "agent_2", "agent_3", "agent_4"
    status: v.string(),
    score: v.optional(v.float64()),
    confidence: v.optional(v.float64()),
    analysisData: v.any(), // JSON data from agent
    timestamp: v.string(),
  }).index("by_token", ["tokenAddress"]),

  system_state: defineTable({
    property: v.string(),
    value: v.string(),
    updatedAt: v.string(),
  }).index("by_property", ["property"]),

  kill_switch: defineTable({
    userId: v.string(),
    tier: v.int64(),
    activeSince: v.optional(v.string()),
    triggerReason: v.optional(v.string()),
    affectedTokens: v.array(v.string()),
    updatedAt: v.string(),
  }).index("by_user", ["userId"]),

  user_profiles: defineTable({
    userId: v.string(),
    userName: v.string(),
    botName: v.string(),
    onboarded: v.boolean(),
    createdAt: v.string(),
  }).index("by_user", ["userId"]),

  chat_history: defineTable({
    userId: v.string(),
    role: v.string(), // "user" or "assistant"
    content: v.string(),
    timestamp: v.string(),
  }).index("by_user", ["userId"]),

  pending_approvals: defineTable({
    proposalId: v.string(),
    userId: v.string(),
    actionJson: v.string(),
    reasoning: v.string(),
    agentVotes: v.string(),
    status: v.string(), // "PENDING", "APPROVED", "REJECTED"
    createdAt: v.string(),
    resolvedAt: v.optional(v.string()),
  }).index("by_proposal", ["proposalId"]),
});
