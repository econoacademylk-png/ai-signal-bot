const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let backendProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    title: "TaizerCodeCrafter AI BOT",
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    autoHideMenuBar: true
  });

  // Check if we are in development mode
  const isDev = !app.isPackaged;

  if (isDev) {
    // In dev, load localhost from Vite
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
    
    // Also start the Python backend (assuming pyinstaller built it)
    const backendPath = path.join(__dirname, '../../backend/dist/main/main.exe');
    backendProcess = spawn(backendPath, [], { detached: false });
  } else {
    // In production, load built React files
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
    
    // Start Python backend bundled with the app
    const backendPath = path.join(process.resourcesPath, 'backend', 'main.exe');
    backendProcess = spawn(backendPath, [], { detached: false });
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Kill the python backend when Electron closes
app.on('will-quit', () => {
  if (backendProcess) {
    backendProcess.kill();
  }
});
