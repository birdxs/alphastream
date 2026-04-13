// Input: 后端对话列表API + chat-store状态
// Output: 对话历史侧边栏UI，支持新建/切换/删除（含确认）对话，加载骨架屏，错误可视化，搜索高亮
// Pos: 首页左侧侧边栏，三栏布局的导航侧
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { apiClient } from "@/lib/api/client";
import { useChatStore } from "@/lib/stores/chat-store";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, MessageSquare, Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import type { Conversation } from "@/lib/types";

/** 搜索关键词高亮：将匹配部分用品牌色 span 包裹 */
function HighlightText({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();
  const idx = lowerText.indexOf(lowerQuery);
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <span className="text-[#3737CC] font-medium">{text.slice(idx, idx + query.length)}</span>
      {text.slice(idx + query.length)}
    </>
  );
}

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

/* ---------- 左滑删除项（移动端） ---------- */
function SwipeableConvItem({
  conv,
  isActive,
  pendingDelete,
  onSelect,
  onDelete,
  searchQuery = '',
}: {
  conv: Conversation;
  isActive: boolean;
  pendingDelete: string | null;
  onSelect: (conv: Conversation) => void;
  onDelete: (id: string) => void;
  searchQuery?: string;
}) {
  const startX = useRef(0);
  const currentX = useRef(0);
  const [offsetX, setOffsetX] = useState(0);
  const [swiping, setSwiping] = useState(false);
  const threshold = 60;

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    startX.current = e.touches[0].clientX;
    currentX.current = startX.current;
    setSwiping(true);
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (!swiping) return;
    currentX.current = e.touches[0].clientX;
    const delta = startX.current - currentX.current;
    // 只允许左滑（delta > 0），带阻尼
    if (delta > 0) {
      setOffsetX(Math.min(delta * 0.6, 100));
    } else {
      setOffsetX(0);
    }
  }, [swiping]);

  const handleTouchEnd = useCallback(() => {
    setSwiping(false);
    if (offsetX >= threshold) {
      // 超过阈值，执行删除
      onDelete(conv.conversation_id);
    }
    setOffsetX(0);
  }, [offsetX, conv.conversation_id, onDelete]);

  return (
    <div className="relative overflow-hidden rounded-lg">
      {/* 红色删除背景 */}
      <div
        className="absolute inset-y-0 right-0 flex items-center justify-center bg-[#EF4444] text-white text-xs font-medium transition-opacity"
        style={{
          width: `${Math.max(offsetX, 0)}px`,
          opacity: offsetX > 20 ? 1 : 0,
        }}
      >
        {offsetX >= threshold ? "释放删除" : <Trash2 className="h-4 w-4" />}
      </div>
      {/* 前景对话项 */}
      <div
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onClick={() => { if (offsetX < 5) onSelect(conv); }}
        className={`relative flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs cursor-pointer group transition-transform duration-150 ${
          isActive
            ? 'bg-[#3737CC]/10 text-[#4F4FE6]'
            : 'text-foreground dark:text-[#F0F0F5]/80 hover:bg-foreground/[0.04] dark:hover:bg-white/[0.04]'
        }`}
        style={{ transform: `translateX(-${offsetX}px)`, backgroundColor: offsetX > 0 ? 'rgba(15,15,35,0.95)' : undefined }}
      >
        <MessageSquare className={`h-3 w-3 shrink-0 ${isActive ? 'text-[#3737CC]' : 'text-[#555570]'}`} />
        <span className="flex-1 truncate">
          {conv.stock_codes && conv.stock_codes.length > 0 && (
            <span className="text-[#3737CC] font-mono text-[11px] font-medium mr-1">{conv.stock_codes[0]}</span>
          )}
          <HighlightText text={conv.title} query={searchQuery} />
        </span>
      </div>
    </div>
  );
}

export function ConversationSidebar({ isMobileSheet = false, onConversationSelect }: { isMobileSheet?: boolean; onConversationSelect?: () => void }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const activeConversationId = useChatStore(s => s.activeConversationId);
  const setActiveConversation = useChatStore(s => s.setActiveConversation);
  const setMessages = useChatStore(s => s.setMessages);

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
    // 在mobile sheet中，选择对话后立即关闭sheet
    onConversationSelect?.();
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

  // 左滑删除（移动端直接执行）
  const swipeDeleteConversation = useCallback(async (id: string) => {
    try {
      await apiClient.delete(`/api/conversations/${id}`);
      setConversations(prev => prev.filter(c => c.conversation_id !== id));
      if (activeConversationId === id) newConversation();
    } catch { showError('删除失败'); }
  }, [activeConversationId]);

  // Mobile Sheet模式下不支持折叠
  if (collapsed && !isMobileSheet) {
    return (
      <div className="hidden sm:flex w-10 bg-[rgba(15,15,35,0.6)] backdrop-blur-2xl border-r border-foreground/[0.08] dark:border-white/[0.08] flex-col items-center py-2 gap-2 transition-all duration-300 ease-in-out">
        <Button variant="ghost" size="icon" onClick={() => setCollapsed(false)} className="text-muted-foreground dark:text-[#8888A0] hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06]" aria-label="展开侧边栏">
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={newConversation} title="新对话" className="text-white hover:bg-[#4F4FE6]/20" aria-label="新建对话">
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className={`${isMobileSheet ? 'w-full h-full' : 'hidden sm:flex w-56 xl:w-64'} flex flex-col bg-[rgba(15,15,35,0.6)] backdrop-blur-2xl ${isMobileSheet ? '' : 'border-r border-foreground/[0.08] dark:border-white/[0.08]'} transition-all duration-300 ease-in-out`}>
      <div className="p-2 border-b border-foreground/[0.08] dark:border-white/[0.08] flex items-center justify-between shrink-0">
        <Button size="sm" onClick={newConversation} className="flex-1 mr-1 gap-1 text-xs bg-[#3737CC] hover:bg-[#4F4FE6] text-white shadow-lg shadow-[#3737CC]/20" aria-label="创建新对话" tabIndex={2}>
          <Plus className="h-3 w-3" />新对话
        </Button>
        {!isMobileSheet && (
          <Button variant="ghost" size="icon" onClick={() => setCollapsed(true)} className="h-7 w-7 text-muted-foreground dark:text-[#8888A0] hover:bg-foreground/[0.06] dark:hover:bg-white/[0.06]" aria-label="收起侧边栏">
            <ChevronLeft className="h-3 w-3" />
          </Button>
        )}
      </div>
      <div className="px-2 py-1.5 shrink-0">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索对话..."
          aria-label="搜索对话"
          tabIndex={1}
          className="w-full bg-foreground/[0.03] dark:bg-white/[0.03] rounded-lg px-2.5 py-1.5 text-[11px] text-foreground dark:text-[#F0F0F5] border border-foreground/[0.08] dark:border-white/[0.08] focus:outline-none focus:ring-1 focus:ring-[#3737CC]/30 focus:border-[#3737CC] transition-all duration-200 placeholder:text-[#555570]"
        />
      </div>
      {error && (
        <div className="mx-2 mt-1 px-2 py-1 bg-[#FF8767]/10 text-[#FF8767] text-[10px] rounded-md border border-[#FF8767]/20">
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
            <div className="flex flex-col items-center text-center py-6 px-3 gap-2">
              <MessageSquare className="h-6 w-6 text-[#3737CC]/30" />
              <p className="text-xs text-[#555570] leading-relaxed">{searchQuery ? '无匹配对话' : '开始一段新对话，探索AI金融分析的无限可能'}</p>
            </div>
          ) : (
            Object.entries(groupByDate(filteredConversations)).map(([label, convs]) => (
              <div key={label} className="mb-1" role="list" aria-label={`${label}的对话`}>
                <div className={`px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase ${
                  label === '今天' ? 'text-[#3737CC]' : label === '昨天' ? 'text-muted-foreground dark:text-[#8888A0]/70' : 'text-[#555570]'
                }`}>{label}</div>
                {convs.map(conv => (
                  isMobileSheet ? (
                    <SwipeableConvItem
                      key={conv.conversation_id}
                      conv={conv}
                      isActive={activeConversationId === conv.conversation_id}
                      pendingDelete={pendingDelete}
                      onSelect={selectConversation}
                      onDelete={swipeDeleteConversation}
                      searchQuery={searchQuery}
                    />
                  ) : (
                  <div
                    key={conv.conversation_id}
                    onClick={() => selectConversation(conv)}
                    tabIndex={3}
                    role="button"
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectConversation(conv); } }}
                    className={`relative flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs cursor-pointer group transition-all duration-150 ${
                      activeConversationId === conv.conversation_id
                        ? 'bg-[#3737CC]/10 text-[#4F4FE6] before:absolute before:left-0 before:top-1 before:bottom-1 before:w-[2px] before:bg-[#3737CC] before:rounded-full before:transition-all before:duration-300 before:ease-out animate-[glass-enter_250ms_ease-out_both]'
                        : 'text-foreground dark:text-[#F0F0F5]/80 hover:bg-foreground/[0.04] dark:hover:bg-white/[0.04] active:animate-[glass-enter_200ms_ease-out_both]'
                    }`}
                  >
                    <MessageSquare className={`h-3 w-3 shrink-0 ${activeConversationId === conv.conversation_id ? 'text-[#3737CC]' : 'text-[#555570]'}`} />
                    <span className="flex-1 truncate">
                      {conv.stock_codes && conv.stock_codes.length > 0 && (
                        <span className="text-[#3737CC] font-mono text-[11px] font-medium mr-1">{conv.stock_codes[0]}</span>
                      )}
                      <HighlightText text={conv.title} query={searchQuery} />
                    </span>
                    <Button
                      variant="ghost" size="icon"
                      className={`h-5 w-5 rounded-md transition-all duration-150 ${pendingDelete === conv.conversation_id ? 'opacity-100 bg-[#FF8767]/10 text-[#FF8767] hover:bg-[#FF8767]/20' : 'opacity-0 group-hover:opacity-100 hover:bg-[#FF8767]/10 hover:text-[#FF8767]'}`}
                      onClick={(e) => deleteConversation(conv.conversation_id, e)}
                      aria-label={pendingDelete === conv.conversation_id ? `确认删除对话: ${conv.title}` : `删除对话: ${conv.title}`}
                    >
                      {pendingDelete === conv.conversation_id ? <span className="text-[10px] font-medium">确认</span> : <Trash2 className="h-3 w-3" />}
                    </Button>
                  </div>
                  )
                ))}
              </div>
            ))
          );
          })()}
        </div>
      </ScrollArea>
      <div className="px-3 py-1.5 border-t border-foreground/[0.08] dark:border-white/[0.08] shrink-0">
        <span className="text-[9px] text-[#555570]/60 tracking-wide">StockAnal v1.0</span>
      </div>
    </div>
  );
}
