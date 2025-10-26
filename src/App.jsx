import React from "react";
import AIConsoleUI from "./AIConsoleUI";
import ChatBox from "./ChatBox";

export default function App() {
  // 💡 Sample AI simulation behavior
  const sendToBackend = async (userText) => {
    userText = userText.toLowerCase();

    if (userText.includes("hello") || userText.includes("hi")) {
      return "Hello! 👋 How can I help you today?";
    }

    if (userText.includes("name")) {
      return "I'm your AI assistant UI demo. You can later connect me to OpenAI 🤖";
    }

    if (userText.includes("help")) {
      return "Sure! You can ask me questions, or type 'record' to see how analysis works.";
    }

    if (userText.includes("record")) {
      return "To start recording audio, click the Start Recording button above. After you stop, I will process the data.";
    }

    if (userText.includes("joke")) {
      return "Why don't programmers like nature? 🐛 Too many bugs!";
    }

    // Default echo response
    return `You said: "${userText}". (This is a sample AI response. You can connect a real backend API next.)`;
  };

  return (
    <div className="container">
      <AIConsoleUI />
      <ChatBox title="Chat" onSend={sendToBackend} />
    </div>
  );
}
