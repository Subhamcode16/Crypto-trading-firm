import './global.css';
import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, RefreshControl, SafeAreaView } from 'react-native';
import { StatusBar } from 'expo-status-bar';

// Set this in .env (e.g. EXPO_PUBLIC_API_URL=https://your-app.onrender.com)
const API_URL = process.env.EXPO_PUBLIC_API_URL || 'http://192.168.1.100:8000';

export default function App() {
  const [data, setData] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const fetchData = async () => {
    try {
      const response = await fetch(`${API_URL}/api/agent/status`);
      const json = await response.json();
      setData(json);
      setError('');
    } catch (err) {
      setError(`Failed to connect to ${API_URL}`);
    }
  };

  const onRefresh = React.useCallback(() => {
    setRefreshing(true);
    fetchData().finally(() => setRefreshing(false));
  }, []);

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <SafeAreaView className="flex-1 bg-white">
      <StatusBar style="dark" />
      <ScrollView
        contentContainerStyle={{ flexGrow: 1, padding: 16 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <Text className="text-3xl font-comic font-black text-center mb-6 [-webkit-text-stroke:1px_black] text-yellow-400">
          FRINK'S LAB
        </Text>

        {error ? (
          <View className="bg-red-100 p-4 border-2 border-black rounded-xl shadow-[4px_4px_0px_rgba(0,0,0,1)]">
            <Text className="text-red-600 font-bold font-comic">{error}</Text>
          </View>
        ) : !data ? (
          <Text className="text-center font-comic">Loading terminal data...</Text>
        ) : (
          <>
            {/* Balance Card */}
            <View className="bg-yellow-400 border-4 border-black p-4 mb-6 shadow-[4px_4px_0px_rgba(0,0,0,1)] rounded-xl">
              <Text className="font-comic font-bold text-xl uppercase">Vault Balance</Text>
              <Text className="text-4xl font-black font-comic text-radioactive-green [-webkit-text-stroke:1px_black]">
                ${(data.gamification?.virtual_balance || 0).toFixed(2)}
              </Text>
            </View>

            {/* Active Positions */}
            <View className="bg-white border-4 border-black p-4 mb-6 shadow-[4px_4px_0px_rgba(0,0,0,1)] rounded-xl">
              <Text className="font-comic font-bold text-xl uppercase border-b-2 border-black pb-2 mb-4">Active Experiments</Text>
              {data.positions && data.positions.length > 0 ? (
                data.positions.map((pos, i) => (
                  <View key={i} className="mb-4 bg-gray-100 p-3 border-2 border-black rounded-lg flex-row justify-between">
                    <View>
                      <Text className="font-black text-lg">{pos.symbol}</Text>
                      <Text className="font-bold text-gray-600">{pos.side.toUpperCase()}</Text>
                    </View>
                    <View className="items-end">
                      <Text className="font-bold text-lg">${(pos.value_usdt || 0).toFixed(2)}</Text>
                      <Text className={`font-black text-lg [-webkit-text-stroke:1px_black] ${pos.unrealized_pnl >= 0 ? 'text-radioactive-green' : 'text-burns-red'}`}>
                        {pos.unrealized_pnl >= 0 ? '+' : ''}${(pos.unrealized_pnl || 0).toFixed(2)}
                      </Text>
                    </View>
                  </View>
                ))
              ) : (
                <Text className="font-comic text-gray-500">No active positions.</Text>
              )}
            </View>

            {/* AI Log (Recent Trades) */}
            <View className="bg-white border-4 border-black p-4 mb-6 shadow-[4px_4px_0px_rgba(0,0,0,1)] rounded-xl">
              <Text className="font-comic font-bold text-xl uppercase border-b-2 border-black pb-2 mb-4">Frink's Rationale</Text>
              {data.trade_history && data.trade_history.length > 0 ? (
                data.trade_history.slice(-3).map((trade, i) => (
                  <View key={i} className="mb-3 border-b-2 border-dashed border-gray-300 pb-2">
                    <Text className="font-bold text-lg">{trade.symbol} - {trade.type}</Text>
                    <Text className="text-gray-600">Price: ${trade.price?.toFixed(2)}</Text>
                  </View>
                ))
              ) : (
                <Text className="font-comic text-gray-500">No recent trades.</Text>
              )}
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
