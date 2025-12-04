import { useState } from "react";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { InputGroupButton } from "@/components/ui/input-group";

type Role = "user" | "aiAssistant";

interface ChatMessage {
  id: number;
  role: Role;
  content: string;
}

function App() {
  const [subject, setSubject] = useState("");
  const [input, setInput] = useState("");
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 1,
      role: "aiAssistant",
      content:
        "Hi, ich bin dein KI Assistent. Ich helfe mit der Informationsaufnahme und Prozessdokumentation. Kannst du mir bisschen über deine Rolle und dein Organisation sagen?",
    },
  ]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const trimmed = input.trim();
    if (!trimmed) return;

    const userMessage: ChatMessage = {
      id: Date.now(),
      role: "user",
      content: trimmed,
    };

    const fakeBotReply: ChatMessage = {
      id: Date.now() + 1,
      role: "aiAssistant",
      content:
        "Danke, ich habe deine Antwort gespeichert. Später kommt hier die echte Mistral Antwort.",
    };

    setMessages((prev) => [...prev, userMessage, fakeBotReply]);
    setInput("");
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadedFile(file);

    const fileMessage: ChatMessage = {
      id: Date.now(),
      role: "user",
      content: `📁 Datei hochgeladen: ${file.name}`,
    };

    setMessages((prev) => [...prev, fileMessage]);
  }

  return (
    <div className="h-screen w-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-4xl h-[90vh] flex flex-col border border-primary shadow-lg">
        <CardHeader className="space-y-3 border-b shrink-0">
          <div className="flex items-center gap-2">
            <div className="flex-1">
              <p className="text-sm font-semibold text-slate-900">
                42° AI Assistant
              </p>
              <p className="text-xs text-slate-500">
                Ihr Assistent zur Informationsaufnahme.
              </p>
            </div>
          </div>

          <div className="mt-2">
            <Input
              placeholder="Betreff / Projektname eingeben..."
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>
        </CardHeader>

        <CardContent className="flex-1 min-h-0 flex flex-col gap-3">
          <div className="flex-1 min-h-0 overflow-y-auto pr-2">
            <div className="space-y-3">
              {messages.map((msg) => {
                const isUser = msg.role === "user";

                return (
                  <div
                    key={msg.id}
                    className={`flex items-start gap-2 ${
                      isUser ? "" : "justify-end"
                    }`}
                  >
                    {isUser && (
                      <Avatar className="h-9 w-9">
                        <AvatarImage src="/" alt="user" />
                        <AvatarFallback>Du</AvatarFallback>
                      </Avatar>
                    )}
                    <div
                      className={`rounded-lg px-3 py-2 text-sm max-w-[75%] ${
                        isUser
                          ? "bg-white border border-slate-200 text-slate-900"
                          : "bg-[#313192] text-white"
                      }`}
                    >
                      {msg.content}
                    </div>
                    {!isUser && (
                      <Avatar className="h-9 w-9">
                        <AvatarImage src="/42AI-logo.png" alt="aiAssistant" />
                        <AvatarFallback>42°AI</AvatarFallback>
                      </Avatar>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <Separator />

          <form
            className="flex gap-3 items-center shrink-0"
            onSubmit={handleSubmit}
          >
            <input
              type="file"
              id="fileInput"
              className="hidden"
              onChange={handleFileUpload}
            />

            <InputGroupButton
              type="button"
              variant="default"
              className="rounded-full h-9 w-9 flex items-center justify-center"
              size="icon-xs"
              onClick={() => document.getElementById("fileInput")?.click()}
            >
              +
            </InputGroupButton>

            <Textarea
              className="flex-1 resize-none max-h-27 overflow-y-auto"
              placeholder="Schreib deine nächste Antwort..."
              rows={3}
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <Button type="submit">Senden</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default App;
