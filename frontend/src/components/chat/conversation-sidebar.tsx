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
      <div className="w-10 border-r flex flex-col items-center py-2 gap-2">
        <Button variant="ghost" size="icon" onClick={() => setCollapsed(false)}>
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={newConversation} title="新对话">
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="w-56 border-r flex flex-col bg-muted/20">
      <div className="p-2 border-b flex items-center justify-between">
        <Button variant="outline" size="sm" onClick={newConversation} className="flex-1 mr-1 gap-1 text-xs">
          <Plus className="h-3 w-3" />新对话
        </Button>
        <Button variant="ghost" size="icon" onClick={() => setCollapsed(true)} className="h-7 w-7">
          <ChevronLeft className="h-3 w-3" />
        </Button>
      </div>
      {error && (
        <div className="mx-2 mt-1 px-2 py-1 bg-red-500/10 text-red-500 text-[10px] rounded">
          {error}
        </div>
      )}
      <ScrollArea className="flex-1">
        <div className="p-1 space-y-0.5">
          {loading ? (
            <div className="p-2 space-y-2">
              {[1,2,3].map(i => <Skeleton key={i} className="h-8 w-full rounded" />)}
            </div>
          ) : conversations.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">暂无对话记录</p>
          ) : (
            Object.entries(groupByDate(conversations)).map(([label, convs]) => (
              <div key={label}>
                <div className="px-2 py-1 text-[10px] text-muted-foreground/60 font-medium uppercase">{label}</div>
                {convs.map(conv => (
                  <div
                    key={conv.conversation_id}
                    onClick={() => selectConversation(conv)}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs cursor-pointer group transition-colors ${
                      activeConversationId === conv.conversation_id
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-muted'
                    }`}
                  >
                    <MessageSquare className="h-3 w-3 shrink-0" />
                    <span className="flex-1 truncate">{conv.title}</span>
                    <Button
                      variant="ghost" size="icon"
                      className={`h-5 w-5 ${pendingDelete === conv.conversation_id ? 'opacity-100 text-red-500' : 'opacity-0 group-hover:opacity-100'} transition-opacity`}
                      onClick={(e) => deleteConversation(conv.conversation_id, e)}
                    >
                      {pendingDelete === conv.conversation_id ? <span className="text-[10px]">确认</span> : <Trash2 className="h-3 w-3" />}
                    </Button>
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
