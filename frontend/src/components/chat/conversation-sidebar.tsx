// Input: 后端对话列表API + chat-store状态
// Output: 对话历史侧边栏UI，支持新建/切换/删除对话
// Pos: 首页左侧侧边栏，三栏布局的导航侧
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api/client";
import { useChatStore } from "@/lib/stores/chat-store";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Plus, MessageSquare, Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import type { Conversation } from "@/lib/types";

export function ConversationSidebar() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const { activeConversationId, setActiveConversation, setMessages } = useChatStore();

  // 加载对话列表
  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    try {
      const data = await apiClient.get<{conversations: Conversation[]}>('/api/conversations');
      setConversations(data.conversations);
    } catch {
      // 忽略错误
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
      // 忽略
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
      // 忽略
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
      <ScrollArea className="flex-1">
        <div className="p-1 space-y-0.5">
          {conversations.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">暂无对话记录</p>
          ) : (
            conversations.map(conv => (
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
                  className="h-5 w-5 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => deleteConversation(conv.conversation_id, e)}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
