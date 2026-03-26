// Input: 后端对话列表API + chat-store状态
// Output: 对话历史侧边栏UI，支持新建/切换/删除（含确认）对话，加载骨架屏，错误可视化
// Pos: 首页左侧侧边栏，三栏布局的导航侧
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api/client";
import { useChatStore } from "@/lib/stores/chat-store";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, MessageSquare, Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import type { Conversation } from "@/lib/types";

const groupByDate = (convs: Conversation[]) => {
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();
  const groups: Record<string, Conversation[]> = {};

  convs.forEach(c => {
    const date = new Date(c.updated_at || c.created_at).toDateString();
    const label = date === today ? '今天' : date === yesterday ? '昨天' : '更早';
    (groups[label] ??= []).push(c);
  });
  return groups;
};

export function ConversationSidebar() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const { activeConversationId, setActiveConversation, setMessages } = useChatStore();

  const showError = (msg: string) => {
    setError(msg);
    setTimeout(() => setError(null), 3000);
  };

  // 加载对话列表
  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{conversations: Conversation[]}>('/api/conversations');
      setConversations(data.conversations);
    } catch {
      showError('加载对话列表失败');
    } finally {
      setLoading(false);
    }
  };

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
      showError('加载对话消息失败');
    }
  };

  const deleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (pendingDelete === id) {
      // 已确认，执行删除
      try {
        await apiClient.delete(`/api/conversations/${id}`);
        setConversations(prev => prev.filter(c => c.conversation_id !== id));
        if (activeConversationId === id) newConversation();
      } catch { showError('删除失败'); }
      setPendingDelete(null);
    } else {
      // 首次点击，显示确认
      setPendingDelete(id);
      setTimeout(() => setPendingDelete(null), 3000);
    }
  };

  if (collapsed) {
    return (
      <div className="w-10 border-r bg-muted/10 flex flex-col items-center py-2 gap-2 transition-all duration-300 ease-in-out">
        <Button variant="ghost" size="icon" onClick={() => setCollapsed(false)} className="hover:bg-muted">
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={newConversation} title="新对话" className="text-primary hover:bg-primary/10">
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="w-56 border-r flex flex-col bg-muted/10 transition-all duration-300 ease-in-out">
      <div className="p-2 border-b border-border/50 flex items-center justify-between shrink-0">
        <Button size="sm" onClick={newConversation} className="flex-1 mr-1 gap-1 text-xs bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm" aria-label="创建新对话" tabIndex={2}>
          <Plus className="h-3 w-3" />新对话
        </Button>
        <Button variant="ghost" size="icon" onClick={() => setCollapsed(true)} className="h-7 w-7 hover:bg-muted">
          <ChevronLeft className="h-3 w-3" />
        </Button>
      </div>
      <div className="px-2 py-1.5 shrink-0">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索对话..."
          aria-label="搜索对话"
          tabIndex={1}
          className="w-full bg-muted/40 rounded-lg px-2.5 py-1.5 text-[11px] border border-border/30 shadow-inner focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/30 focus:bg-background transition-all duration-200 placeholder:text-muted-foreground/40"
        />
      </div>
      {error && (
        <div className="mx-2 mt-1 px-2 py-1 bg-red-500/10 text-red-500 text-[10px] rounded-md border border-red-500/20">
          {error}
        </div>
      )}
      <ScrollArea className="flex-1">
        <div className="p-1 space-y-0.5">
          {loading ? (
            <div className="p-2 space-y-2">
              {[1,2,3].map(i => <Skeleton key={i} className="h-8 w-full rounded-md" />)}
            </div>
          ) : (() => {
            const filteredConversations = searchQuery
              ? conversations.filter(c => c.title.toLowerCase().includes(searchQuery.toLowerCase()))
              : conversations;
            return filteredConversations.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">{searchQuery ? '无匹配对话' : '暂无对话记录'}</p>
          ) : (
            Object.entries(groupByDate(filteredConversations)).map(([label, convs]) => (
              <div key={label} className="mb-1">
                <div className={`px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase ${
                  label === '今天' ? 'text-primary/70' : label === '昨天' ? 'text-muted-foreground/70' : 'text-muted-foreground/50'
                }`}>{label}</div>
                {convs.map(conv => (
                  <div
                    key={conv.conversation_id}
                    onClick={() => selectConversation(conv)}
                    tabIndex={3}
                    role="button"
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectConversation(conv); } }}
                    className={`relative flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs cursor-pointer group transition-all duration-150 ${
                      activeConversationId === conv.conversation_id
                        ? 'bg-primary/10 text-primary before:absolute before:left-0 before:top-1 before:bottom-1 before:w-[2px] before:bg-primary before:rounded-full'
                        : 'hover:bg-muted/80'
                    }`}
                  >
                    <MessageSquare className={`h-3 w-3 shrink-0 ${activeConversationId === conv.conversation_id ? 'text-primary' : 'text-muted-foreground/50'}`} />
                    <span className="flex-1 truncate">
                      {conv.stock_codes && conv.stock_codes.length > 0 && (
                        <span className="text-primary font-mono text-[11px] font-medium mr-1">{conv.stock_codes[0]}</span>
                      )}
                      {conv.title}
                    </span>
                    <Button
                      variant="ghost" size="icon"
                      className={`h-5 w-5 rounded-md transition-all duration-150 ${pendingDelete === conv.conversation_id ? 'opacity-100 bg-red-500/10 text-red-500 hover:bg-red-500/20' : 'opacity-0 group-hover:opacity-100 hover:bg-red-500/10 hover:text-red-500'}`}
                      onClick={(e) => deleteConversation(conv.conversation_id, e)}
                    >
                      {pendingDelete === conv.conversation_id ? <span className="text-[10px] font-medium">确认</span> : <Trash2 className="h-3 w-3" />}
                    </Button>
                  </div>
                ))}
              </div>
            ))
          );
          })()}
        </div>
      </ScrollArea>
      <div className="px-3 py-1.5 border-t border-border/30 shrink-0">
        <span className="text-[9px] text-muted-foreground/30 tracking-wide">StockAnal v1.0</span>
      </div>
    </div>
  );
}
