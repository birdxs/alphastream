// Input: chat-store对话状态 + 后端对话列表API
// Output: 移动端侧边抽屉导航菜单，含对话历史列表
// Pos: components/layout/mobile-drawer.tsx - 移动端导航抽屉
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect } from "react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Menu, MessageSquare, Briefcase, Star, Settings, Plus, Trash2, ChevronDown, ChevronRight, BarChart3 } from "lucide-react";
import Link from "next/link";
import { apiClient } from "@/lib/api/client";
import { useChatStore } from "@/lib/stores/chat-store";
import type { Conversation } from "@/lib/types";

export function MobileDrawer() {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const activeConversationId = useChatStore(s => s.activeConversationId);
  const setActiveConversation = useChatStore(s => s.setActiveConversation);
  const setMessages = useChatStore(s => s.setMessages);

  const loadConversations = async () => {
    try {
      const data = await apiClient.get<{conversations: Conversation[]}>('/api/conversations');
      setConversations(data.conversations);
    } catch {
      setError('加载失败');
      setTimeout(() => setError(null), 3000);
    }
  };

  useEffect(() => {
    if (historyOpen && conversations.length === 0) {
      loadConversations();
    }
  }, [historyOpen, conversations.length]);

  const newConversation = () => {
    setActiveConversation(null);
    setMessages([]);
    useChatStore.getState().clearArtifacts();
    useChatStore.getState().resetStreamContent();
    useChatStore.getState().setFollowUps([]);
  };

  const selectConversation = async (conv: Conversation) => {
    setActiveConversation(conv.conversation_id);
    try {
      const data = await apiClient.get<{messages: Array<{message_id: string; role: 'user' | 'assistant' | 'system'; content: string; created_at: string}>}>(`/api/conversations/${conv.conversation_id}`);
      if (data.messages) {
        setMessages(data.messages);
      }
    } catch {
      setError('加载消息失败');
      setTimeout(() => setError(null), 3000);
    }
  };

  const deleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiClient.delete(`/api/conversations/${id}`);
      setConversations(prev => prev.filter(c => c.conversation_id !== id));
      if (activeConversationId === id) {
        newConversation();
      }
    } catch {
      setError('删除失败');
      setTimeout(() => setError(null), 3000);
    }
  };

  return (
    <Sheet>
      <SheetTrigger
        render={
          <Button variant="ghost" size="icon" className="sm:hidden" />
        }
      >
        <Menu className="h-5 w-5" />
      </SheetTrigger>
      <SheetContent side="left" className="w-64 p-0">
        <div className="p-4 border-b">
          <h2 className="font-bold text-lg flex items-center gap-2">
            <span className="text-primary">AI</span>金融分析
          </h2>
        </div>
        {error && (
          <div className="mx-2 mt-1 px-2 py-1 bg-[#FF8767]/10 text-[#FF8767] text-[10px] rounded">
            {error}
          </div>
        )}
        <nav className="p-2 space-y-1">
          {[
            { href: "/", icon: MessageSquare, label: "AI对话" },
            { href: "/portfolio", icon: Briefcase, label: "投资组合" },
            { href: "/watchlist", icon: Star, label: "自选股" },
            { href: "/compare", icon: BarChart3, label: "多股对比" },
            { href: "/settings", icon: Settings, label: "设置" },
          ].map(item => (
            <Link key={item.href} href={item.href}>
              <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-accent transition-colors">
                <item.icon className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">{item.label}</span>
              </div>
            </Link>
          ))}

          {/* 对话历史折叠区 */}
          <div className="pt-2 border-t mt-2">
            <button
              onClick={() => setHistoryOpen(!historyOpen)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-accent transition-colors w-full text-left"
            >
              {historyOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
              <span className="text-sm">对话历史</span>
            </button>
            {historyOpen && (
              <div className="pl-2">
                <button
                  onClick={newConversation}
                  className="flex items-center gap-2 px-3 py-1.5 rounded text-xs hover:bg-accent transition-colors w-full text-left text-primary"
                >
                  <Plus className="h-3 w-3" />
                  新对话
                </button>
                <ScrollArea className="max-h-48">
                  {conversations.length === 0 ? (
                    <p className="text-[10px] text-muted-foreground text-center py-2">暂无记录</p>
                  ) : (
                    conversations.map(conv => (
                      <div
                        key={conv.conversation_id}
                        onClick={() => selectConversation(conv)}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs cursor-pointer group transition-colors ${
                          activeConversationId === conv.conversation_id
                            ? 'bg-primary/10 text-primary'
                            : 'hover:bg-muted'
                        }`}
                      >
                        <MessageSquare className="h-3 w-3 shrink-0" />
                        <span className="flex-1 truncate">{conv.title}</span>
                        <Button
                          variant="ghost" size="icon"
                          className="h-5 w-5 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => deleteConversation(conv.conversation_id, e)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    ))
                  )}
                </ScrollArea>
              </div>
            )}
          </div>
        </nav>
      </SheetContent>
    </Sheet>
  );
}
