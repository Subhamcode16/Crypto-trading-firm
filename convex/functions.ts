import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// --- Signals ---
export const logSignal = mutation({
  args: {
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
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("signals", args);
  },
});

export const getSignalByToken = query({
  args: { tokenAddress: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("signals")
      .withIndex("by_tokenAndTimestamp", (q) => q.eq("tokenAddress", args.tokenAddress))
      .order("desc")
      .first();
  },
});

// --- Trades ---
export const logTrade = mutation({
  args: {
    tradeId: v.string(),
    userId: v.string(), // Added
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
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("trades", args);
  },
});

export const updateTrade = mutation({
  args: {
    tradeId: v.string(),
    updates: v.any(),
  },
  handler: async (ctx, args) => {
    const trade = await ctx.db
      .query("trades")
      .filter((q) => q.eq(q.field("tradeId"), args.tradeId))
      .first();

    if (trade) {
      await ctx.db.patch(trade._id, args.updates);
      return trade._id;
    }
    return null;
  },
});

// --- Agent Intel ---
export const saveIntel = mutation({
  args: {
    tokenAddress: v.string(),
    agentType: v.string(),
    status: v.string(),
    score: v.optional(v.float64()),
    confidence: v.optional(v.float64()),
    analysisData: v.any(),
    timestamp: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("agent_intel")
      .withIndex("by_token", (q) => q.eq("tokenAddress", args.tokenAddress))
      .filter((q) => q.eq(q.field("agentType"), args.agentType))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, args);
      return existing._id;
    }
    return await ctx.db.insert("agent_intel", args);
  },
});

// --- System State ---
export const setSystemState = mutation({
  args: {
    property: v.string(),
    value: v.string(),
    updatedAt: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("system_state")
      .withIndex("by_property", (q) => q.eq("property", args.property))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, { value: args.value, updatedAt: args.updatedAt });
    } else {
      await ctx.db.insert("system_state", args);
    }
  },
});

export const getSystemState = query({
  args: { property: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("system_state")
      .withIndex("by_property", (q) => q.eq("property", args.property))
      .first();
  },
});

// --- Pending Approvals ---
export const createPendingApproval = mutation({
  args: {
    proposalId: v.string(),
    userId: v.string(),
    actionJson: v.string(),
    reasoning: v.string(),
    agentVotes: v.string(),
    status: v.string(),
    createdAt: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("pending_approvals", args);
  },
});

export const updatePendingApproval = mutation({
  args: {
    proposalId: v.string(),
    status: v.string(),
    resolvedAt: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("pending_approvals")
      .filter((q) => q.eq(q.field("proposalId"), args.proposalId))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, { status: args.status, resolvedAt: args.resolvedAt });
    }
  },
});

// --- User Profiles ---
export const saveProfile = mutation({
  args: {
    userId: v.string(),
    userName: v.string(),
    botName: v.string(),
    onboarded: v.boolean(),
    createdAt: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("user_profiles")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, args);
      return existing._id;
    }
    return await ctx.db.insert("user_profiles", args);
  },
});

export const getProfile = query({
  args: { userId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("user_profiles")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .first();
  },
});

// --- Chat History ---
export const appendChatHistory = mutation({
  args: {
    userId: v.string(),
    role: v.string(),
    content: v.string(),
    timestamp: v.string(),
  },
  handler: async (ctx, args) => {
    await ctx.db.insert("chat_history", args);

    // Keep last 20 messages
    const history = await ctx.db
      .query("chat_history")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .order("desc")
      .collect();

    if (history.length > 20) {
      const toDelete = history.slice(20);
      for (const msg of toDelete) {
        await ctx.db.delete(msg._id);
      }
    }
  },
});

export const getChatHistory = query({
  args: { userId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("chat_history")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .order("asc")
      .collect();
  },
});

export const clearChatHistory = mutation({
  args: { userId: v.string() },
  handler: async (ctx, args) => {
    const history = await ctx.db
      .query("chat_history")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .collect();

    for (const msg of history) {
      await ctx.db.delete(msg._id);
    }
  },
});
export const getPositions = query({
  args: { userId: v.string() },
  handler: async (ctx, args) => {
    const trades = await ctx.db
      .query("trades")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .collect();

    return {
      open: trades.filter((t) => t.status === "OPEN"),
      closed: trades.filter((t) => t.status === "CLOSED"),
    };
  },
});

export const getKillSwitch = query({
  args: { userId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("kill_switch")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .first();
  },
});

export const setKillSwitch = mutation({
  args: {
    userId: v.string(),
    tier: v.int64(),
    reason: v.string(),
    actor: v.string(),
    affectedTokens: v.array(v.string()),
    activeSince: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("kill_switch")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        tier: args.tier,
        triggerReason: args.reason,
        affectedTokens: args.affectedTokens,
        activeSince: args.activeSince,
        updatedAt: new Date().toISOString(),
      });
    } else {
      await ctx.db.insert("kill_switch", {
        ...args,
        triggerReason: args.reason,
        updatedAt: new Date().toISOString(),
      });
    }
  },
});

export const clearKillSwitch = mutation({
  args: {
    userId: v.string(),
    actor: v.string(),
    resolvedAt: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("kill_switch")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .first();

    if (existing) {
      await ctx.db.delete(existing._id);
    }
  },
});

export const getRecentAnalysis = query({
  args: { tokenAddress: v.string(), cutoffTime: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("agent_intel")
      .withIndex("by_token", (q) => q.eq("tokenAddress", args.tokenAddress))
      .filter((q) => q.gte(q.field("timestamp"), args.cutoffTime))
      .order("desc")
      .first();
  },
});

export const getDailyStats = query({
  args: { userId: v.string(), date: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("daily_stats")
      .withIndex("by_user_date", (q) => q.eq("userId", args.userId).eq("date", args.date))
      .first();
  },
});

export const updateDailyStats = mutation({
  args: {
    userId: v.string(),
    date: v.string(),
    updates: v.any(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("daily_stats")
      .withIndex("by_user_date", (q) => q.eq("userId", args.userId).eq("date", args.date))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        ...args.updates,
        updatedAt: new Date().toISOString(),
      });
    } else {
      await ctx.db.insert("daily_stats", {
        userId: args.userId,
        date: args.date,
        realizedPnlUsd: args.updates.realizedPnlUsd || 0,
        realizedLossUsd: args.updates.realizedLossUsd || 0,
        dailyLossLimitUsd: args.updates.dailyLossLimitUsd || 0,
        updatedAt: new Date().toISOString(),
      });
    }
  },
});

export const getUserProfiles = query({
  args: { onboardedOnly: v.optional(v.boolean()) },
  handler: async (ctx, args) => {
    let q = ctx.db.query("user_profiles");
    if (args.onboardedOnly) {
      q = q.filter((q) => q.eq(q.field("onboarded"), true));
    }
    return await q.collect();
  },
});
