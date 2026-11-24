"use client";

import SuggestionCard from "./SuggestionCard";

// Message bubble supporting user messages and assistant replies with suggestion cards
export default function ChatMessage({ message, onAddSuggestion, disabled }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"} mb-4`}>
      <div
        className={`max-w-[85%] sm:max-w-[75%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? "bg-indigo-600 text-white rounded-br-none"
            : "bg-white text-gray-800 border border-gray-200 shadow-sm rounded-bl-none"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>

      {/* Render structured suggestion cards when returned by the backend */}
      {!isUser && message.suggestions && message.suggestions.length > 0 && (
        <div className="w-full mt-2.5 grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-[95%]">
          {message.suggestions.map((item) => (
            <SuggestionCard
              key={item.item_id}
              item={item}
              onAdd={onAddSuggestion}
              disabled={disabled}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Bouncing dots animation indicating the assistant is generating a response
export function TypingIndicator() {
  return (
    <div className="flex items-center space-x-1.5 p-3 max-w-[75px] bg-white border border-gray-200 rounded-2xl rounded-bl-none shadow-sm mb-4">
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
    </div>
  );
}
