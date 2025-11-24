// Interview-Orchestrator Web-App JavaScript
// Leichtgewichtige Implementierung mit Streaming-Support

class InterviewApp {
  constructor() {
    this.sessionId = this.generateSessionId();
    this.currentQuestion = null;
    this.init();
  }

  generateSessionId() {
    return 'session_' + Date.now() + '_' +
        Math.random().toString(36).substr(2, 9);
  }

  init() {
    this.setupEventListeners();
    this.startInterview();
    this.updateStatus();
    this.loadUploadedFiles();
  }

  setupEventListeners() {
    // Send-Button und Enter-Taste
    const sendBtn = document.getElementById('send-btn');
    const answerInput = document.getElementById('answer-input');

    sendBtn.addEventListener('click', () => this.submitAnswer());
    answerInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        this.submitAnswer();
      }
    });

    // Reset-Button
    document.getElementById('reset-btn').addEventListener('click', () => {
      if (confirm(
              'Möchten Sie das Interview wirklich neu starten? Alle bisherigen Antworten gehen verloren.')) {
        this.resetInterview();
      }
    });

    // File Upload
    const fileInput = document.getElementById('file-input');
    const selectFilesBtn = document.getElementById('select-files-btn');
    const uploadArea = document.getElementById('upload-area');

    selectFilesBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.click();
    });
    fileInput.addEventListener(
        'change', (e) => this.handleFileSelect(e.target.files));

    // Drag & Drop
    uploadArea.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadArea.classList.add('drag-over');
    });

    uploadArea.addEventListener('dragleave', () => {
      uploadArea.classList.remove('drag-over');
    });

    uploadArea.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadArea.classList.remove('drag-over');
      this.handleFileSelect(e.dataTransfer.files);
    });

    uploadArea.addEventListener('click', (e) => {
      if (e.target.id !== 'select-files-btn') {
        fileInput.click();
      }
    });
  }

  async startInterview() {
    try {
      // Zeige Lade-Status
      this.showProcessStatus('Initialisiere Interview...');

      const response = await fetch('/api/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({session_id: this.sessionId})
      });

      const data = await response.json();

      if (data.success && data.question) {
        this.hideProcessStatus();
        this.displayQuestion(data.question);
        this.updateStatus(data.status);
      }
    } catch (error) {
      console.error('Error starting interview:', error);
      this.hideProcessStatus();
      this.showSystemMessage(
          'Fehler beim Starten des Interviews. Bitte laden Sie die Seite neu.');
    }
  }

  async submitAnswer() {
    const answerInput = document.getElementById('answer-input');
    const answer = answerInput.value.trim();

    if (!answer || !this.currentQuestion) {
      return;
    }

    // Zeige Antwort im Chat
    this.displayAnswer(answer);

    // Eingabefeld leeren und deaktivieren
    answerInput.value = '';
    answerInput.disabled = true;

    try {
      // Zeige Verarbeitungs-Status
      this.showProcessStatus('Verarbeite Antwort...');

      const response = await fetch('/api/answer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: this.sessionId,
          question_id: this.currentQuestion.id,
          answer: answer
        })
      });

      const data = await response.json();

      if (data.success) {
        // Zeige spezifischen Prozess-Status falls vorhanden
        if (data.process_status) {
          this.showProcessStatus(data.process_status);
          // Kurze Verzögerung damit der User den Status sieht
          await new Promise(resolve => setTimeout(resolve, 800));
        }

        this.updateStatus(data.status);

        if (data.completed) {
          this.hideProcessStatus();
          this.showSystemMessage(
              'Interview abgeschlossen! Vielen Dank für Ihre Antworten.');
          answerInput.disabled = true;
        } else if (data.question) {
          this.hideProcessStatus();
          this.displayQuestion(data.question);
          answerInput.disabled = false;
          answerInput.focus();
        }
      }
    } catch (error) {
      console.error('Error submitting answer:', error);
      this.hideProcessStatus();
      this.showSystemMessage(
          'Fehler beim Senden der Antwort. Bitte versuchen Sie es erneut.');
      answerInput.disabled = false;
    }
  }

  displayQuestion(question) {
    this.currentQuestion = question;

    const chatMessages = document.getElementById('chat-messages');
    const currentQuestionDiv = document.getElementById('current-question');

    // Zeige Frage im Chat-Verlauf
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message question';

    let questionHtml = `<div class="message-label">Frage</div>`;
    questionHtml += `<div class="message-text">${question.text}</div>`;

    // Optionen werden nicht mehr angezeigt - User kann frei antworten

    messageDiv.innerHTML = questionHtml;
    chatMessages.appendChild(messageDiv);

    // Setze aktuelle Frage
    currentQuestionDiv.textContent = question.text;

    // Scroll nach unten
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  displayAnswer(answer) {
    const chatMessages = document.getElementById('chat-messages');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message answer';
    messageDiv.innerHTML = `
            <div class="message-label">Ihre Antwort</div>
            <div class="message-text">${this.escapeHtml(answer)}</div>
        `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  showSystemMessage(message) {
    const chatMessages = document.getElementById('chat-messages');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system';
    messageDiv.innerHTML = `<div class="message-text">${message}</div>`;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async updateStatus(status = null) {
    if (!status) {
      try {
        const response =
            await fetch(`/api/status?session_id=${this.sessionId}`);
        const data = await response.json();
        if (data.success) {
          status = data.status;
        }
      } catch (error) {
        console.error('Error fetching status:', error);
        return;
      }
    }

    if (status) {
      document.getElementById('status-phase').textContent = status.phase_label;
      document.getElementById('status-role').textContent = status.role_label;
      document.getElementById('status-questions').textContent =
          status.answered_questions;
      document.getElementById('status-files').textContent =
          status.uploaded_files_count;

      // Hervorheben bei niedriger Konfidenz
      const roleElement = document.getElementById('status-role');
      if (status.role_confidence_low) {
        roleElement.style.color = '#ff9800';
        roleElement.title = 'Rollenzuordnung unsicher';
      } else {
        roleElement.style.color = '';
        roleElement.title = '';
      }
    }
  }

  async resetInterview() {
    try {
      const response = await fetch('/api/reset', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({session_id: this.sessionId})
      });

      const data = await response.json();

      if (data.success) {
        // Lösche Chat-Verlauf
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.innerHTML = `
                    <div class="welcome-message">
                        <h3>Willkommen!</h3>
                        <p>Ich helfe Ihnen dabei, Ihre Geschäftsprozesse zu dokumentieren.</p>
                        <p>Bitte beantworten Sie die folgenden Fragen so detailliert wie möglich.</p>
                    </div>
                `;

        // Zeige erste Frage
        if (data.question) {
          this.displayQuestion(data.question);
        }

        // Aktualisiere Status
        this.updateStatus(data.status);

        // Aktiviere Eingabefeld
        document.getElementById('answer-input').disabled = false;
        document.getElementById('answer-input').focus();

        this.showSystemMessage('Interview wurde neu gestartet.');
      }
    } catch (error) {
      console.error('Error resetting interview:', error);
      this.showSystemMessage(
          'Fehler beim Zurücksetzen. Bitte laden Sie die Seite neu.');
    }
  }

  async handleFileSelect(files) {
    for (const file of files) {
      await this.uploadFile(file);
    }
  }

  async uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', this.sessionId);

    try {
      const response =
          await fetch('/api/upload', {method: 'POST', body: formData});

      const data = await response.json();

      if (data.success) {
        this.showSystemMessage(`Datei "${file.name}" wurde hochgeladen.`);
        this.addFileToList(data.file);
        this.updateStatus();
      } else {
        this.showSystemMessage(
            `Fehler beim Hochladen von "${file.name}": ${data.message}`);
      }
    } catch (error) {
      console.error('Error uploading file:', error);
      this.showSystemMessage(`Fehler beim Hochladen von "${file.name}".`);
    }
  }

  async loadUploadedFiles() {
    try {
      const response = await fetch(`/api/files?session_id=${this.sessionId}`);
      const data = await response.json();

      if (data.success && data.files.length > 0) {
        const filesList = document.getElementById('files-list');
        filesList.innerHTML = '';

        data.files.forEach(file => {
          this.addFileToList(file);
        });
      }
    } catch (error) {
      console.error('Error loading files:', error);
    }
  }

  addFileToList(file) {
    const filesList = document.getElementById('files-list');

    const li = document.createElement('li');
    li.className = 'file-item';

    const sizeKB = (file.size / 1024).toFixed(2);

    li.innerHTML = `
            <span class="file-icon">■</span>
            <div class="file-info">
                <div class="file-name">${this.escapeHtml(file.filename)}</div>
                <div class="file-size">${sizeKB} KB</div>
            </div>
        `;

    filesList.appendChild(li);
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  showProcessStatus(message) {
    const processActivity = document.getElementById('process-activity');
    const processMessage = document.getElementById('process-message');

    processMessage.textContent = message;
    processActivity.style.display = 'block';
  }

  hideProcessStatus() {
    const processActivity = document.getElementById('process-activity');
    processActivity.style.display = 'none';
  }
}

// Starte die App wenn DOM geladen ist
document.addEventListener('DOMContentLoaded', () => {
  window.app = new InterviewApp();
});
