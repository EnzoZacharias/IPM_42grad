import { useState, useEffect, useRef, useCallback } from "react";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { InputGroupButton } from "@/components/ui/input-group";
import {
  startInterview,
  submitAnswer,
  uploadFile,
  getSessionId,
  setSessionId,
  resetSessionId,
  resetInterview,
  getSessions,
  resumeSession,
  deleteSession,
  startNewRoleInterview,
  switchToInterview,
  exportPDF,
  getUploadedFiles,
  deleteFile,
  getLLMStatus,
  switchLLMBackend,
  type Question,
  type InterviewStatus,
  type SessionInfo,
  type HistoryEntry,
  type UploadedFile,
  type LLMBackendStatus,
} from "@/api/interviewApi";

type MessageRole = "user" | "aiAssistant" | "system";

interface ChatMessage {
  id: number;
  role: MessageRole;
  content: string;
  questionId?: string;
  isStreaming?: boolean;
}

type AppView =
  | "loading"
  | "sessionRestore"
  | "roleSelection"
  | "projectName"
  | "chat";

// Project name storage
function getStoredProjectName(): string {
  return localStorage.getItem("interview_project_name") || "";
}

function setStoredProjectName(name: string): void {
  localStorage.setItem("interview_project_name", name);
}

function App() {
  // View state
  const [currentView, setCurrentView] = useState<AppView>("loading");

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [status, setStatus] = useState<InterviewStatus | null>(null);
  const [isInterviewComplete, setIsInterviewComplete] = useState(false);
  const [streamingText, setStreamingText] = useState<string>("");

  // Session state
  const [savedSessions, setSavedSessions] = useState<SessionInfo[]>([]);

  // File state
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);

  // LLM Backend state
  const [llmStatus, setLlmStatus] = useState<LLMBackendStatus | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showRoles, setShowRoles] = useState(false);

  // UI state
  const [processStatus, setProcessStatus] = useState<string | null>(null);
  const [projectName, setProjectName] = useState(getStoredProjectName());
  const [projectNameInput, setProjectNameInput] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const useStreaming = true; // Enable streaming

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  // Scroll to bottom when entering chat view (with delay for rendering)
  useEffect(() => {
    if (currentView === "chat") {
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
      }, 100);
    }
  }, [currentView]);

  // Auto-focus textarea when loading finishes
  useEffect(() => {
    if (!isLoading && currentView === "chat" && !isInterviewComplete) {
      textareaRef.current?.focus();
    }
  }, [isLoading, currentView, isInterviewComplete]);

  // Check for saved sessions on mount
  useEffect(() => {
    checkForSavedSessions();
    loadLLMStatus();
  }, []);

  // Load LLM status
  async function loadLLMStatus() {
    try {
      const response = await getLLMStatus();
      if (response.success && response.status) {
        setLlmStatus(response.status);
      }
    } catch (error) {
      console.error("Error loading LLM status:", error);
    }
  }

  // Load uploaded files
  const loadUploadedFiles = useCallback(async () => {
    try {
      const response = await getUploadedFiles();
      if (response.success && response.files) {
        setUploadedFiles(response.files);
      }
    } catch (error) {
      console.error("Error loading files:", error);
    }
  }, []);

  // Check for saved sessions
  async function checkForSavedSessions() {
    try {
      const response = await getSessions();

      if (
        response.success &&
        response.sessions &&
        response.sessions.length > 0
      ) {
        const currentSessionId = getSessionId();
        const currentSession = response.sessions.find(
          (s) => s.session_id === currentSessionId
        );

        const relevantSessions = response.sessions.filter(
          (s) =>
            s.answered_questions > 0 ||
            (s.completed_interviews && s.completed_interviews > 0)
        );

        if (relevantSessions.length > 0) {
          setSavedSessions(relevantSessions);
          setCurrentView("sessionRestore");
        } else if (currentSession && currentSession.answered_questions > 0) {
          setSavedSessions([currentSession]);
          setCurrentView("sessionRestore");
        } else {
          // Check if we have a project name
          if (getStoredProjectName()) {
            setCurrentView("roleSelection");
          } else {
            setCurrentView("projectName");
          }
        }
      } else {
        // Check if we have a project name
        if (getStoredProjectName()) {
          setCurrentView("roleSelection");
        } else {
          setCurrentView("projectName");
        }
      }
    } catch (error) {
      console.error("Error checking for saved sessions:", error);
      if (getStoredProjectName()) {
        setCurrentView("roleSelection");
      } else {
        setCurrentView("projectName");
      }
    }
  }

  // Save project name and continue
  function handleSaveProjectName() {
    const name = projectNameInput.trim();
    if (!name) return;

    setStoredProjectName(name);
    setProjectName(name);
    setCurrentView("roleSelection");
  }

  // Continue an existing session
  async function handleContinueSession(sessionId: string) {
    setProcessStatus("Lade gespeicherte Session...");
    setCurrentView("loading");

    try {
      const response = await resumeSession(sessionId);

      if (response.success) {
        setSessionId(sessionId);

        // Restore session name from saved sessions
        const sessionInfo = savedSessions.find(
          (s) => s.session_id === sessionId
        );
        if (sessionInfo?.session_name) {
          setProjectName(sessionInfo.session_name);
          setStoredProjectName(sessionInfo.session_name);
        }

        // Restore chat history
        if (response.history && response.history.length > 0) {
          const restoredMessages: ChatMessage[] = [
            {
              id: Date.now(),
              role: "system",
              content: "📋 Interview wurde wiederhergestellt.",
            },
          ];

          response.history.forEach((entry: HistoryEntry, index: number) => {
            if (entry.question) {
              restoredMessages.push({
                id: Date.now() + index * 2,
                role: "aiAssistant",
                content: entry.question,
              });
            }
            if (entry.answer) {
              restoredMessages.push({
                id: Date.now() + index * 2 + 1,
                role: "user",
                content: entry.answer,
              });
            }
          });

          // Prüfe ob die aktuelle Frage bereits in der History ist (letzte unbeantwortete Frage)
          const currentQ = response.current_question || response.question;
          const lastHistoryEntry =
            response.history[response.history.length - 1];
          const isCurrentQuestionInHistory =
            currentQ &&
            lastHistoryEntry &&
            lastHistoryEntry.question === currentQ.text &&
            !lastHistoryEntry.answer;

          // Füge aktuelle Frage nur hinzu, wenn sie noch nicht in der History ist
          if (currentQ && !isCurrentQuestionInHistory) {
            restoredMessages.push({
              id: Date.now() + response.history.length * 2,
              role: "aiAssistant",
              content: currentQ.text,
              questionId: currentQ.id,
            });
          }

          setMessages(restoredMessages);

          if (currentQ) {
            setCurrentQuestion(currentQ);
          }
        } else if (response.current_question || response.question) {
          // Keine History, nur aktuelle Frage
          const question = response.current_question || response.question;
          setCurrentQuestion(question!);
          setMessages([
            {
              id: Date.now(),
              role: "system",
              content: "📋 Interview wurde wiederhergestellt.",
            },
            {
              id: Date.now() + 1,
              role: "aiAssistant",
              content: question!.text,
              questionId: question!.id,
            },
          ]);
        }

        if (response.status) {
          setStatus(response.status);
        }

        await loadUploadedFiles();
        setCurrentView("chat");
      } else {
        addSystemMessage("Fehler beim Laden der Session: " + response.message);
        setCurrentView("roleSelection");
      }
    } catch (error) {
      console.error("Error continuing session:", error);
      addSystemMessage("Fehler beim Laden der Session.");
      setCurrentView("roleSelection");
    } finally {
      setProcessStatus(null);
    }
  }

  // Delete a session
  async function handleDeleteSession(sessionId: string) {
    if (!confirm("Möchten Sie diese Session wirklich löschen?")) {
      return;
    }

    try {
      const response = await deleteSession(sessionId);

      if (response.success) {
        const currentSessionId = getSessionId();
        if (sessionId === currentSessionId) {
          resetSessionId();
        }

        const updatedSessions = savedSessions.filter(
          (s) => s.session_id !== sessionId
        );
        setSavedSessions(updatedSessions);

        if (updatedSessions.length === 0) {
          setCurrentView("roleSelection");
        }
      }
    } catch (error) {
      console.error("Error deleting session:", error);
      addSystemMessage("Fehler beim Löschen der Session.");
    }
  }

  // Start a new session
  async function handleStartNewSession() {
    resetSessionId();
    setMessages([]);
    if (getStoredProjectName()) {
      setCurrentView("roleSelection");
    } else {
      setCurrentView("projectName");
    }
  }

  // Start interview with streaming
  async function startInterviewWithStreaming(role?: string) {
    setCurrentView("chat");
    setIsLoading(true);
    setProcessStatus("Generiere erste Frage...");
    setStreamingText("");

    setMessages([]);

    try {
      const sessionId = getSessionId();
      const response = await fetch("/api/next-question-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          preset_role: role === "auto" ? undefined : role,
        }),
      });

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No reader available");

      const decoder = new TextDecoder();
      let questionText = "";
      let finalQuestion: Question | null = null;
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === "status") {
                setProcessStatus(data.message);
              } else if (data.type === "chunk") {
                questionText += data.text;
                setStreamingText(questionText);
              } else if (data.type === "complete") {
                setProcessStatus(null);
                if (data.question) {
                  finalQuestion = data.question;
                  setCurrentQuestion(data.question);
                  setStatus(data.status);
                  setStreamingText("");
                }
              } else if (data.type === "error") {
                setProcessStatus(null);
                addSystemMessage("Fehler: " + data.message);
              }
            } catch {
              // Ignore parse errors
            }
          }
        }
      }

      if (finalQuestion) {
        setMessages([
          {
            id: Date.now(),
            role: "aiAssistant",
            content: finalQuestion.text,
            questionId: finalQuestion.id,
          },
        ]);
      }

      await loadUploadedFiles();
    } catch (error) {
      console.error("Error with streaming:", error);
      // Fallback to non-streaming
      await startInterviewNonStreaming(role);
    } finally {
      setIsLoading(false);
      setProcessStatus(null);
    }
  }

  // Start interview without streaming (fallback)
  async function startInterviewNonStreaming(role?: string) {
    try {
      const response = await startInterview(role === "auto" ? undefined : role);

      if (response.success && response.question) {
        setCurrentQuestion(response.question);
        setStatus(response.status || null);

        setMessages([
          {
            id: Date.now(),
            role: "aiAssistant",
            content: response.question.text,
            questionId: response.question.id,
          },
        ]);

        await loadUploadedFiles();
      } else {
        addSystemMessage(
          response.message || "Es gab ein Problem beim Starten des Interviews."
        );
      }
    } catch (error) {
      console.error("Failed to initialize interview:", error);
      addSystemMessage("Verbindung zum Server fehlgeschlagen.");
    }
  }

  // Start interview with a specific role
  async function handleStartInterviewWithRole(role: string) {
    if (useStreaming) {
      await startInterviewWithStreaming(role);
    } else {
      setCurrentView("chat");
      setIsLoading(true);
      await startInterviewNonStreaming(role);
      setIsLoading(false);
    }
  }

  // Helper functions to add messages
  function addSystemMessage(content: string) {
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: "system", content },
    ]);
  }

  function addAssistantMessage(content: string, questionId?: string) {
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: "aiAssistant", content, questionId },
    ]);
  }

  function addUserMessage(content: string) {
    setMessages((prev) => [...prev, { id: Date.now(), role: "user", content }]);
  }

  // Submit answer with streaming
  async function submitAnswerWithStreaming(answer: string) {
    if (!currentQuestion) return;

    setIsLoading(true);
    addUserMessage(answer);
    setProcessStatus("Verarbeite Antwort...");
    setStreamingText("");

    try {
      const sessionId = getSessionId();
      const response = await fetch("/api/answer-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          question_id: currentQuestion.id,
          answer: answer,
        }),
      });

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No reader available");

      const decoder = new TextDecoder();
      let questionText = "";
      let buffer = "";
      let pendingQuestion: Question | null = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === "status") {
                setProcessStatus(data.message);
              } else if (data.type === "chunk") {
                questionText += data.text;
                setStreamingText(questionText);
              } else if (data.type === "role_classified") {
                // Rollenklassifizierung separat anzeigen
                setStatus(data.status);
                const confidence = data.status.role_confidence_low
                  ? "(unsicher)"
                  : "(sicher)";
                addSystemMessage(
                  `🎯 Rolle identifiziert: ${
                    data.status.role_label || data.status.role
                  } ${confidence}`
                );
              } else if (data.type === "complete") {
                setProcessStatus(null);
                setStatus(data.status);

                // Interview-Abschluss oder nächste Frage
                if (data.completed) {
                  setStreamingText("");
                  setIsInterviewComplete(true);
                  setCurrentQuestion(null);
                  addAssistantMessage(
                    "🎉 Vielen Dank! Das Interview ist abgeschlossen."
                  );
                } else if (data.question) {
                  // Speichere Frage für verzögerte Anzeige
                  pendingQuestion = data.question;
                  // streamingText bleibt bis die Frage angezeigt wird
                }
              } else if (data.type === "error") {
                setProcessStatus(null);
                addSystemMessage("Fehler: " + data.message);
              }
            } catch {
              // Ignore parse errors
            }
          }
        }
      }

      // Zeige verzögert die nächste Frage an (nach Rollenklassifizierung)
      if (pendingQuestion) {
        await new Promise((resolve) => setTimeout(resolve, 800));
        setStreamingText("");
        setCurrentQuestion(pendingQuestion);
        addAssistantMessage(pendingQuestion.text, pendingQuestion.id);
      } else {
        // Kein pending question - streamingText trotzdem leeren
        setStreamingText("");
      }
    } catch (error) {
      console.error("Streaming error:", error);
      // Fallback to non-streaming
      await submitAnswerNonStreaming(answer);
    } finally {
      setIsLoading(false);
      setProcessStatus(null);
    }
  }

  // Submit answer without streaming (fallback)
  async function submitAnswerNonStreaming(answer: string) {
    if (!currentQuestion) return;

    try {
      const response = await submitAnswer(currentQuestion.id, answer);

      if (response.success) {
        setStatus(response.status || null);

        // Erst Rollenklassifizierung anzeigen (falls vorhanden)
        if (response.role_classified && response.status?.role) {
          addSystemMessage(
            `🎯 Rolle identifiziert: ${
              response.status.role_label || response.status.role
            }`
          );
          // Kurze Verzögerung bevor die nächste Frage erscheint
          await new Promise((resolve) => setTimeout(resolve, 800));
        }

        if (response.completed || !response.question) {
          setIsInterviewComplete(true);
          setCurrentQuestion(null);
          addAssistantMessage(
            "🎉 Vielen Dank! Das Interview ist abgeschlossen."
          );
        } else {
          setCurrentQuestion(response.question);
          addAssistantMessage(response.question.text, response.question.id);
        }
      } else {
        addSystemMessage("Es gab einen Fehler bei der Verarbeitung.");
      }
    } catch (error) {
      console.error("Failed to submit answer:", error);
      addSystemMessage("Verbindungsfehler.");
    }
  }

  // Submit answer
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const trimmed = input.trim();
    if (!trimmed || !currentQuestion || isLoading) return;

    setInput("");

    if (useStreaming) {
      await submitAnswerWithStreaming(trimmed);
    } else {
      setIsLoading(true);
      addUserMessage(trimmed);
      await submitAnswerNonStreaming(trimmed);
      setIsLoading(false);
    }
  }

  // Handle file upload
  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsLoading(true);
    addUserMessage(`📁 Datei: ${file.name}`);

    try {
      const response = await uploadFile(file);

      if (response.success) {
        addAssistantMessage(
          `✅ "${response.file?.filename || file.name}" hochgeladen.`
        );
        await loadUploadedFiles();
      } else {
        addAssistantMessage(`❌ Fehler: ${response.message || "Unbekannt"}`);
      }
    } catch (error) {
      console.error("Failed to upload file:", error);
      addAssistantMessage("❌ Upload fehlgeschlagen.");
    } finally {
      setIsLoading(false);
      e.target.value = "";
    }
  }

  // Handle file deletion
  async function handleDeleteFile(filename: string) {
    try {
      const response = await deleteFile(filename);
      if (response.success) {
        await loadUploadedFiles();
      }
    } catch (error) {
      console.error("Error deleting file:", error);
    }
  }

  // Reset interview
  async function handleResetInterview() {
    if (
      !confirm("Interview wirklich neu starten? Alle Antworten gehen verloren.")
    ) {
      return;
    }

    setIsLoading(true);
    setProcessStatus("Starte Interview neu...");

    try {
      await deleteSession(getSessionId());
      resetSessionId();

      const response = await resetInterview();

      if (response.success) {
        setMessages([
          {
            id: Date.now(),
            role: "system",
            content: "Interview neu gestartet.",
          },
        ]);
        setIsInterviewComplete(false);
        setStatus(response.status || null);

        if (response.question) {
          setCurrentQuestion(response.question);
          addAssistantMessage(response.question.text, response.question.id);
        }
      }
    } catch (error) {
      console.error("Error resetting interview:", error);
      addSystemMessage("Fehler beim Zurücksetzen.");
    } finally {
      setIsLoading(false);
      setProcessStatus(null);
    }
  }

  // Start new role interview
  async function handleNewRoleInterview() {
    if (
      !confirm(
        "Neues Interview für andere Rolle starten?\nAktuelles wird gespeichert."
      )
    ) {
      return;
    }

    setIsLoading(true);
    setProcessStatus("Starte neues Rollen-Interview...");

    try {
      const response = await startNewRoleInterview();

      if (response.success) {
        setMessages([
          {
            id: Date.now(),
            role: "system",
            content: `✅ Neues Interview. (${response.completed_interviews} gespeichert)`,
          },
        ]);
        setIsInterviewComplete(false);
        setStatus(response.status || null);

        if (response.question) {
          setCurrentQuestion(response.question);
          addAssistantMessage(response.question.text, response.question.id);
        }
      } else {
        addSystemMessage("❌ Fehler: " + response.message);
      }
    } catch (error) {
      console.error("Error starting new role interview:", error);
      addSystemMessage("❌ Fehler beim Starten.");
    } finally {
      setIsLoading(false);
      setProcessStatus(null);
    }
  }

  // Switch to a completed interview
  async function handleSwitchInterview(index: number) {
    if (
      !confirm(
        "Zu diesem Interview wechseln?\nAktueller Fortschritt wird gespeichert."
      )
    ) {
      return;
    }

    setIsLoading(true);
    setProcessStatus("Wechsle Interview...");

    try {
      const response = await switchToInterview(index);

      if (response.success) {
        // Restore chat history
        const restoredMessages: ChatMessage[] = [
          {
            id: Date.now(),
            role: "system",
            content: `Gewechselt zu: ${response.switched_to?.role_label}`,
          },
        ];

        if (response.chat_history) {
          let currentQ: string | null = null;
          response.chat_history.forEach((item, idx) => {
            if (item.type === "question") {
              currentQ = item.text || "";
            } else if (item.type === "answer" && currentQ) {
              restoredMessages.push({
                id: Date.now() + idx * 2,
                role: "aiAssistant",
                content: currentQ,
              });
              restoredMessages.push({
                id: Date.now() + idx * 2 + 1,
                role: "user",
                content: item.text || "",
              });
              currentQ = null;
            }
          });
        }

        setMessages(restoredMessages);
        setStatus(response.status || null);

        if (response.next_question) {
          setCurrentQuestion(response.next_question);
          addAssistantMessage(
            response.next_question.text,
            response.next_question.id
          );
        }

        setIsInterviewComplete(false);
      } else {
        addSystemMessage("❌ Fehler: " + response.message);
      }
    } catch (error) {
      console.error("Error switching interview:", error);
      addSystemMessage("❌ Fehler beim Wechseln.");
    } finally {
      setIsLoading(false);
      setProcessStatus(null);
    }
  }

  // Switch LLM backend
  async function handleSwitchBackend(backend: "local" | "mistral_api") {
    setProcessStatus(
      `Wechsle zu ${backend === "local" ? "Lokal" : "Mistral API"}...`
    );

    try {
      const response = await switchLLMBackend(backend);

      if (response.success && response.status) {
        setLlmStatus(response.status);
        addSystemMessage(
          `✅ Backend: ${
            backend === "local" ? "Lokales Modell" : "Mistral API"
          }`
        );
      } else {
        addSystemMessage(
          `⚠️ Backend-Wechsel fehlgeschlagen: ${response.message}`
        );
      }
    } catch (error) {
      console.error("Error switching backend:", error);
      addSystemMessage("❌ Fehler beim Backend-Wechsel");
    } finally {
      setProcessStatus(null);
    }
  }

  // Export as PDF
  async function handleExportPDF() {
    if (!status || status.answered_questions === 0) {
      addSystemMessage("⚠️ Keine Daten vorhanden.");
      return;
    }

    setIsLoading(true);
    setProcessStatus("Generiere PDF...");

    try {
      const blob = await exportPDF();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${projectName || "Prozessdokumentation"}_${new Date()
        .toISOString()
        .slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      addSystemMessage("✅ PDF generiert!");
    } catch (error) {
      console.error("Error exporting PDF:", error);
      addSystemMessage(
        `❌ PDF-Fehler: ${error instanceof Error ? error.message : "Unbekannt"}`
      );
    } finally {
      setIsLoading(false);
      setProcessStatus(null);
    }
  }

  // Format file size
  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  // Render: Project Name Input
  function renderProjectNameView() {
    return (
      <div className="h-screen w-screen flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <h2 className="text-xl font-semibold">📋 Projekt-Information</h2>
            <p className="text-sm text-slate-500">
              Bitte geben Sie einen Projektnamen oder Betreff ein.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              placeholder="z.B. Prozessoptimierung Vertrieb"
              value={projectNameInput}
              onChange={(e) => setProjectNameInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSaveProjectName()}
              autoFocus
            />
            <Button
              className="w-full"
              onClick={handleSaveProjectName}
              disabled={!projectNameInput.trim()}
            >
              Weiter
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Render: Session Restore
  function renderSessionRestoreView() {
    return (
      <div className="h-screen w-screen flex items-center justify-center p-4 ">
        <Card className="w-full max-w-2xl max-h-[80vh] flex flex-col">
          <CardHeader className="shrink-0">
            <h2 className="text-xl font-semibold">
              💾 Gespeicherte Interviews
            </h2>
            <p className="text-sm text-slate-500">
              Fortsetzen oder neu starten?
            </p>
          </CardHeader>
          <CardContent className="space-y-4 overflow-y-auto">
            {savedSessions.map((session) => {
              const date = new Date(session.last_activity);
              const dateStr =
                date.toLocaleDateString("de-DE") +
                " " +
                date.toLocaleTimeString("de-DE", {
                  hour: "2-digit",
                  minute: "2-digit",
                });

              return (
                <div
                  key={session.session_id}
                  className="border rounded-lg p-3 bg-white"
                >
                  <div className="flex justify-between items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium truncate">
                        {session.session_name ||
                          session.role ||
                          "Nicht klassifiziert"}
                      </p>
                      <p className="text-xs text-slate-500">{dateStr}</p>
                      {session.role && session.session_name && (
                        <span className="inline-block bg-indigo-100 text-indigo-800 px-1.5 py-0.5 rounded text-xs mt-1">
                          {session.role}
                        </span>
                      )}
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs">
                          {session.answered_questions} Fragen
                        </span>
                        {session.progress_percent !== undefined && (
                          <span className="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded text-xs">
                            {session.progress_percent}%
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <Button
                        size="sm"
                        onClick={() =>
                          handleContinueSession(session.session_id)
                        }
                      >
                        Fortsetzen
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeleteSession(session.session_id)}
                      >
                        ×
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
            <Separator />
            <Button
              className="w-full"
              variant="outline"
              onClick={handleStartNewSession}
            >
              Neues Interview
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Render: Role Selection
  function renderRoleSelectionView() {
    return (
      <div className="h-screen w-screen flex items-center justify-center p-4 ">
        <Card className="w-full max-w-2xl">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold">🎯 Rolle wählen</h2>
                <p className="text-sm text-slate-500">
                  Projekt: <span className="font-medium">{projectName}</span>
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setProjectNameInput(projectName);
                  setCurrentView("projectName");
                }}
              >
                ✏️
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              {[
                { role: "fach", icon: "👔", label: "Fachabteilung" },
                { role: "it", icon: "💻", label: "IT-Abteilung" },
                { role: "management", icon: "📊", label: "Management" },
                {
                  role: "auto",
                  icon: "🤖",
                  label: "Auto-Erkennung",
                  highlight: true,
                },
              ].map(({ role, icon, label, highlight }) => (
                <Button
                  key={role}
                  className={`h-20 flex flex-col ${
                    highlight
                      ? "bg-[#313192] text-white hover:bg-[#252578]"
                      : ""
                  }`}
                  variant={highlight ? "default" : "outline"}
                  onClick={() => handleStartInterviewWithRole(role)}
                >
                  <span className="text-2xl mb-1">{icon}</span>
                  <span className="text-sm">{label}</span>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Render: Loading
  function renderLoadingView() {
    return (
      <div className="h-screen w-screen flex items-center justify-center p-4 ">
        <Card className="w-full max-w-md">
          <CardContent className="p-8 text-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[#313192] mx-auto mb-4"></div>
            <p className="text-slate-600 text-sm">
              {processStatus || "Laden..."}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Render: Chat
  function renderChatView() {
    const hasCompletedRoles =
      status?.completed_roles && status.completed_roles.length > 0;

    return (
      <div className="h-screen w-screen flex items-center justify-center p-4 ">
        <Card className="w-full max-w-4xl h-[90vh] flex flex-col border border-primary shadow-lg">
          {/* Header */}
          <CardHeader className="space-y-2 border-b shrink-0 py-2">
            {/* Title Row */}
            <div className="flex items-center gap-2">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-slate-900 truncate">
                  {projectName || "42° AI Assistant"}
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-1 shrink-0">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setShowRoles(!showRoles);
                    setShowSettings(false);
                  }}
                  title="Rollen & Interviews"
                  className={`h-8 w-8 p-0 ${showRoles ? "bg-slate-200" : ""}`}
                >
                  👤
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setShowSettings(!showSettings);
                    setShowRoles(false);
                  }}
                  title="Einstellungen"
                  className={`h-8 w-8 p-0 ${
                    showSettings ? "bg-slate-200" : ""
                  }`}
                >
                  ⚙️
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleExportPDF}
                  disabled={
                    isLoading || !status || status.answered_questions === 0
                  }
                  title="PDF exportieren"
                  className="h-8 w-8 p-0"
                >
                  📄
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleResetInterview}
                  disabled={isLoading}
                  title="Interview zurücksetzen"
                  className="h-8 w-8 p-0"
                >
                  🔄
                </Button>
              </div>
            </div>

            {/* Rollen Panel */}
            {showRoles && (
              <div className="bg-slate-50 rounded-lg p-3 space-y-3 text-xs">
                {/* Aktuelle Rolle */}
                <div>
                  <p className="font-medium text-slate-700 mb-1">
                    Aktuelle Rolle
                  </p>
                  <div className="bg-[#313192] text-white px-3 py-2 rounded flex items-center justify-between">
                    <span className="font-medium">
                      {status?.role_label || "Rolle wird erkannt..."}
                    </span>
                    {status?.progress && (
                      <span className="bg-white/20 px-2 py-0.5 rounded">
                        {status.progress.percent}%
                      </span>
                    )}
                  </div>
                </div>

                {/* Neues Interview starten */}
                <div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleNewRoleInterview}
                    disabled={isLoading || !status?.role}
                    className="w-full text-xs h-8"
                  >
                    ➕ Neues Rollen-Interview starten
                  </Button>
                </div>

                {/* Abgeschlossene Interviews */}
                {hasCompletedRoles && (
                  <div>
                    <p className="font-medium text-slate-700 mb-1">
                      Abgeschlossene Interviews (
                      {status!.completed_roles.length})
                    </p>
                    <div className="space-y-1">
                      {status!.completed_roles.map((role, idx) => (
                        <button
                          key={idx}
                          onClick={() => {
                            handleSwitchInterview(idx);
                            setShowRoles(false);
                          }}
                          className="w-full flex items-center justify-between bg-white px-2 py-1.5 rounded border border-slate-200 hover:bg-green-50 hover:border-green-300 transition-colors"
                        >
                          <span>👤 {role.role_label}</span>
                          <span className="text-green-600 font-medium">
                            {role.progress_percent}% ✓
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Settings Panel - LLM, Dokumente */}
            {showSettings && (
              <div className="bg-slate-50 rounded-lg p-3 space-y-3 text-xs">
                {/* LLM Backend */}
                <div>
                  <p className="font-medium text-slate-700 mb-1">LLM Backend</p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant={
                        llmStatus?.current === "local" ? "default" : "outline"
                      }
                      onClick={() => handleSwitchBackend("local")}
                      disabled={!llmStatus?.local.available}
                      className={`flex-1 text-xs h-8 ${
                        llmStatus?.current === "local"
                          ? "ring-2 ring-green-500 ring-offset-1"
                          : ""
                      }`}
                    >
                      <span className="flex flex-col items-center">
                        <span>
                          {llmStatus?.local.available ? "✓" : "✗"} Lokal
                        </span>
                        {llmStatus?.current === "local" && (
                          <span className="text-[10px] opacity-80">
                            {llmStatus.local.model}
                          </span>
                        )}
                      </span>
                    </Button>
                    <Button
                      size="sm"
                      variant={
                        llmStatus?.current === "mistral_api"
                          ? "default"
                          : "outline"
                      }
                      onClick={() => handleSwitchBackend("mistral_api")}
                      disabled={!llmStatus?.mistral_api.has_key}
                      className={`flex-1 text-xs h-8 ${
                        llmStatus?.current === "mistral_api"
                          ? "ring-2 ring-green-500 ring-offset-1"
                          : ""
                      }`}
                    >
                      <span className="flex flex-col items-center">
                        <span>
                          {llmStatus?.mistral_api.has_key ? "✓" : "✗"} Mistral
                          API
                        </span>
                        {llmStatus?.current === "mistral_api" && (
                          <span className="text-[10px] opacity-80">
                            {llmStatus.mistral_api.model}
                          </span>
                        )}
                      </span>
                    </Button>
                  </div>
                </div>

                {/* Dokumente */}
                {uploadedFiles.length > 0 && (
                  <div>
                    <p className="font-medium text-slate-700 mb-1">
                      Dokumente ({uploadedFiles.length})
                    </p>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {uploadedFiles.map((file) => (
                        <div
                          key={file.filename}
                          className="flex items-center justify-between bg-white px-2 py-1 rounded border border-slate-200"
                        >
                          <span
                            className="truncate flex-1"
                            title={file.filename}
                          >
                            {file.filename}
                          </span>
                          <div className="flex items-center gap-2 ml-2 shrink-0">
                            <span className="text-slate-400">
                              {formatFileSize(file.size)}
                            </span>
                            <button
                              onClick={() => handleDeleteFile(file.filename)}
                              className="text-red-400 hover:text-red-600"
                              title="Löschen"
                            >
                              ✗
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Aktuelle Rolle - kompakt in einer Zeile */}
            <div className="flex items-center gap-2 text-xs">
              <span className="bg-[#313192] text-white px-2 py-1 rounded font-medium">
                {status?.role_label || "Rolle wird erkannt..."}
              </span>
              {status?.progress && (
                <span className="text-slate-500">
                  {status.progress.percent}%
                </span>
              )}
              {status && (
                <span className="text-slate-400">
                  • {status.answered_questions} Fragen
                </span>
              )}
              {hasCompletedRoles && (
                <span className="text-green-600">
                  • {status!.completed_roles.length} abgeschl.
                </span>
              )}
              {uploadedFiles.length > 0 && (
                <span className="text-slate-400">
                  • {uploadedFiles.length} Dok.
                </span>
              )}
            </div>

            {/* Progress bar */}
            {status?.progress && (
              <div className="w-full bg-slate-200 rounded-full h-1.5">
                <div
                  className="h-1.5 rounded-full transition-all duration-300"
                  style={{
                    width: `${status.progress.percent}%`,
                    backgroundColor: status.progress.is_complete
                      ? "#4caf50"
                      : status.progress.percent >= 50
                      ? "#2196f3"
                      : "#ff9800",
                  }}
                />
              </div>
            )}
          </CardHeader>

          {/* Chat Messages */}
          <CardContent className="flex-1 min-h-0 flex flex-col gap-2 p-3">
            <div className="flex-1 min-h-0 overflow-y-auto pr-1">
              <div className="space-y-2">
                {messages.map((msg) => {
                  if (msg.role === "system") {
                    return (
                      <div
                        key={msg.id}
                        className="text-center text-xs text-slate-500 py-1.5 bg-slate-50 rounded"
                      >
                        {msg.content}
                      </div>
                    );
                  }

                  const isUser = msg.role === "user";

                  return (
                    <div
                      key={msg.id}
                      className={`flex items-start gap-2 ${
                        isUser ? "justify-end" : "justify-start"
                      }`}
                    >
                      {!isUser && (
                        <Avatar className="h-8 w-8">
                          <AvatarImage src="/42AI-logo.png" alt="AI" />
                          <AvatarFallback className="text-xs">
                            42°
                          </AvatarFallback>
                        </Avatar>
                      )}

                      <div
                        className={`rounded-lg px-3 py-2 text-sm max-w-[75%] whitespace-pre-wrap ${
                          isUser
                            ? "bg-[#313192] text-white"
                            : "bg-white border border-slate-200 text-slate-900"
                        }`}
                      >
                        {msg.content}
                      </div>

                      {isUser && (
                        <Avatar className="h-8 w-8">
                          <AvatarFallback className="text-xs">
                            Du
                          </AvatarFallback>
                        </Avatar>
                      )}
                    </div>
                  );
                })}

                {/* Streaming text */}
                {streamingText && (
                  <div className="flex items-start gap-2 justify-start">
                    <div className="rounded-lg px-3 py-2 text-sm max-w-[75%] bg-[#313192] text-white whitespace-pre-wrap">
                      {streamingText}
                      <span className="animate-pulse">|</span>
                    </div>
                    <Avatar className="h-8 w-8">
                      <AvatarImage src="/42AI-logo.png" alt="AI" />
                      <AvatarFallback className="text-xs">42°</AvatarFallback>
                    </Avatar>
                  </div>
                )}

                {/* Loading indicator */}
                {isLoading && !streamingText && (
                  <div className="flex items-start gap-2 justify-end">
                    <div className="rounded-lg px-3 py-2 text-sm bg-[#313192] text-white">
                      <span className="animate-pulse">...</span>
                    </div>
                    <Avatar className="h-8 w-8">
                      <AvatarImage src="/42AI-logo.png" alt="AI" />
                      <AvatarFallback className="text-xs">42°</AvatarFallback>
                    </Avatar>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </div>

            <Separator />

            {/* Input Form */}
            <form
              className="flex gap-2 items-center shrink-0"
              onSubmit={handleSubmit}
            >
              <input
                type="file"
                id="fileInput"
                className="hidden"
                accept=".pdf,.txt"
                onChange={handleFileUpload}
              />

              <InputGroupButton
                type="button"
                variant="default"
                className="rounded-full h-8 w-8 flex items-center justify-center text-sm"
                size="icon-xs"
                onClick={() => document.getElementById("fileInput")?.click()}
                disabled={isLoading}
              >
                +
              </InputGroupButton>

              <Textarea
                ref={textareaRef}
                className="flex-1 resize-none max-h-24 overflow-y-auto text-sm"
                placeholder={
                  isInterviewComplete ? "Abgeschlossen" : "Antwort eingeben..."
                }
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={isLoading || isInterviewComplete}
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
              />
              <Button
                type="submit"
                disabled={isLoading || isInterviewComplete || !input.trim()}
                size="sm"
              >
                {isLoading ? "..." : "➤"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Main render
  switch (currentView) {
    case "loading":
      return renderLoadingView();
    case "sessionRestore":
      return renderSessionRestoreView();
    case "projectName":
      return renderProjectNameView();
    case "roleSelection":
      return renderRoleSelectionView();
    case "chat":
      return renderChatView();
    default:
      return renderLoadingView();
  }
}

export default App;
