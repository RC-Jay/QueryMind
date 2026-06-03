import ChatInterface from "@/components/chat/ChatInterface";

export default async function ChatPage({ params }: { params: Promise<{ id?: string[] }> }) {
  const { id } = await params;
  const conversationId = id?.[0];
  return <ChatInterface conversationId={conversationId} />;
}
