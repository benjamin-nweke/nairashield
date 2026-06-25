import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Shield, Lock, LogOut, Send, AlertTriangle, CheckCircle, Info, 
  Activity, Users, Settings, Plus, RefreshCw, ChevronDown, ChevronUp, UserCheck,
  ArrowRight, Cpu, Database, Sparkles, Terminal, Layers, Sun, Moon,
  Eye, EyeOff, User, Mail, Key, ShieldCheck, BadgeCheck, ChevronRight,
  FileText, Download
} from 'lucide-react';
import confetti from 'canvas-confetti';

const BASE_URL = ''; // Proxied via Vite

const SVGGauge = ({ value }) => {
  const percentage = Math.min(Math.max((value || 0) * 100, 0), 100);
  const radius = 50;
  const strokeWidth = 8;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  let strokeColor = "#10B981"; // default green
  if (percentage >= 85) {
    strokeColor = "#EF4444"; // red
  } else if (percentage >= 50) {
    strokeColor = "#F59E0B"; // orange/amber
  } else if (percentage >= 20) {
    strokeColor = "#C9A84C"; // gold
  }

  return (
    <div className="relative flex flex-col items-center justify-center">
      <svg className="w-36 h-36 transform -rotate-90">
        <circle
          cx="72"
          cy="72"
          r={radius}
          fill="transparent"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx="72"
          cy="72"
          r={radius}
          fill="transparent"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          style={{
            transition: "stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1), stroke 0.8s ease",
            filter: `drop-shadow(0 0 4px ${strokeColor})`
          }}
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className="text-3xl font-extrabold" style={{ color: strokeColor }}>
          {percentage.toFixed(1)}%
        </span>
        <span className="text-[10px] text-gray-400 font-semibold tracking-wider uppercase mt-1">
          Fraud Risk
        </span>
      </div>
    </div>
  );
};

export default function App() {
  const [authToken, setAuthToken] = useState(localStorage.getItem('access_token'));
  const [username, setUsername] = useState(localStorage.getItem('username'));
  const [role, setRole] = useState(localStorage.getItem('role'));
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [currentView, setCurrentView] = useState(localStorage.getItem('access_token') ? 'dashboard' : 'landing');
  const [sandboxAmount, setSandboxAmount] = useState(750000);
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');

  // Sync theme class to document root
  useEffect(() => {
    if (theme === 'light') {
      document.documentElement.classList.add('light');
    } else {
      document.documentElement.classList.remove('light');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  // Registration & User creation state hooks
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [registerUsername, setRegisterUsername] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState('');
  const [registerRole, setRegisterRole] = useState('Viewer');
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [showRegPassword, setShowRegPassword] = useState(false);
  const [showRegConfirm, setShowRegConfirm] = useState(false);
  const [provisionUsername, setProvisionUsername] = useState('');
  const [provisionPassword, setProvisionPassword] = useState('');
  const [provisionRole, setProvisionRole] = useState('Analyst');
  const [provisionLoading, setProvisionLoading] = useState(false);

  // Dashboard states
  const [amount, setAmount] = useState('2125000');
  const [channel, setChannel] = useState('channel_TRANSFER');
  const [source, setSource] = useState('source_dataset_PaySim');
  const [profiling, setProfiling] = useState(false);
  const [profilingResult, setProfilingResult] = useState(null);
  const [showShapDetails, setShowShapDetails] = useState(true);

  // Config threshold state
  const [threshold, setThreshold] = useState(0.50);
  const [configLoading, setConfigLoading] = useState(false);



  // Authenticated fetch wrapper
  const authenticatedFetch = async (url, options = {}) => {
    let token = authToken;
    if (!options.headers) {
      options.headers = {};
    }
    if (token) {
      options.headers['Authorization'] = `Bearer ${token}`;
    }

    let response = await fetch(url, options);

    if (response.status === 401) {
      // Access token expired, try to refresh
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const refreshRes = await fetch('/api/auth/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
          });
          if (refreshRes.ok) {
            const data = await refreshRes.json();
            localStorage.setItem('access_token', data.access_token);
            setAuthToken(data.access_token);
            options.headers['Authorization'] = `Bearer ${data.access_token}`;
            // Retry initial fetch
            response = await fetch(url, options);
          } else {
            handleLogout();
            throw new Error("Session expired. Please login again.");
          }
        } catch (e) {
          handleLogout();
          throw e;
        }
      } else {
        handleLogout();
      }
    }
    return response;
  };

  // Auth Functions
  const handleLogin = async (e) => {
    if (e) e.preventDefault();
    setLoginError('');
    setAuthLoading(true);
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUsername, password: loginPassword })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Authentication failed');
      }
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      localStorage.setItem('username', data.username);
      localStorage.setItem('role', data.role);
      setAuthToken(data.access_token);
      setUsername(data.username);
      setRole(data.role);
      setCurrentView('dashboard');
    } catch (err) {
      setLoginError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const quickLogin = (user, pass) => {
    setLoginUsername(user);
    setLoginPassword(pass);
    // Execute login with state updates
    setTimeout(() => {
      setLoginError('');
      setAuthLoading(true);
      fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: user, password: pass })
      })
      .then(res => {
        if (!res.ok) return res.json().then(data => { throw new Error(data.error) });
        return res.json();
      })
      .then(data => {
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        localStorage.setItem('username', data.username);
        localStorage.setItem('role', data.role);
        setAuthToken(data.access_token);
        setUsername(data.username);
        setRole(data.role);
        setCurrentView('dashboard');
      })
      .catch(err => setLoginError(err.message))
      .finally(() => setAuthLoading(false));
    }, 50);
  };

  const handleLogout = async () => {
    if (authToken) {
      try {
        await authenticatedFetch('/api/auth/logout', { method: 'POST' });
      } catch (e) {}
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    setAuthToken(null);
    setUsername(null);
    setRole(null);
    setProfilingResult(null);
    setCurrentView('landing');
  };

  const handleRegister = async (e) => {
    if (e) e.preventDefault();
    setLoginError('');
    
    if (registerPassword !== registerConfirmPassword) {
      setLoginError("Confirmation password does not match original password.");
      return;
    }

    if (!acceptTerms) {
      setLoginError("Please review and accept the operator compliance agreement.");
      return;
    }

    setAuthLoading(true);
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          username: registerUsername, 
          password: registerPassword, 
          role: registerRole 
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Registration failed');
      }
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      localStorage.setItem('username', data.username);
      localStorage.setItem('role', data.role);
      setAuthToken(data.access_token);
      setUsername(data.username);
      setRole(data.role);
      setIsRegisterMode(false);
      setCurrentView('dashboard');
      
      // Clear registration inputs
      setRegisterUsername('');
      setRegisterPassword('');
      setRegisterConfirmPassword('');
      setAcceptTerms(false);

      // Celebrate!
      confetti({
        particleCount: 100,
        spread: 70,
        origin: { y: 0.8 }
      });
    } catch (err) {
      setLoginError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleProvisionUser = async (e) => {
    e.preventDefault();
    if (!provisionUsername || !provisionPassword) {
      alert("Username and password are required");
      return;
    }
    setProvisionLoading(true);
    try {
      const res = await authenticatedFetch('/api/admin/create-user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: provisionUsername,
          password: provisionPassword,
          role: provisionRole
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Failed to provision user');
      }
      alert(data.message);
      setProvisionUsername('');
      setProvisionPassword('');
      setProvisionRole('Analyst');
    } catch (err) {
      alert(err.message);
    } finally {
      setProvisionLoading(false);
    }
  };

  // Profile Transaction
  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    setProfiling(true);
    
    // Scale amount exactly like backend expects (min-max between 0 and 2,500,000 NGN)
    const rawAmt = parseFloat(amount);
    const scaledAmt = Math.min(rawAmt / 2500000.0, 1.0);

    const payload = {
      amount: scaledAmt,
      channel_CARD_HOST: 0,
      channel_CARD_WEB: 0,
      channel_DEBIT: 0,
      channel_PAYMENT: 0,
      channel_TRANSFER: 0,
      "source_dataset_IEEE-CIS": 0,
      source_dataset_PaySim: 0
    };

    payload[channel] = 1;
    payload[source] = 1;

    try {
      const res = await authenticatedFetch('/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || 'Profiling failed');
      }
      const data = await res.json();
      setProfilingResult(data);

      // Trigger success celebration if prediction is safe/approved
      if (data.prediction === 0) {
        confetti({
          particleCount: 80,
          spread: 60,
          origin: { y: 0.8 },
          colors: ['#C9A84C', '#10B981', '#ffffff']
        });
      }

    } catch (err) {
      alert(err.message);
    } finally {
      setProfiling(false);
    }
  };

  // Update Threshold Config
  const handleThresholdUpdate = async () => {
    setConfigLoading(true);
    try {
      const res = await authenticatedFetch('/api/admin/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fraud_threshold: threshold })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || 'Failed to update threshold');
      }
      const data = await res.json();
      alert(`${data.message} (Cutoff: ${data.fraud_threshold.toFixed(2)})`);
    } catch (err) {
      alert(err.message);
    } finally {
      setConfigLoading(false);
    }
  };



  // Clean formatting helpers
  const formatNaira = (val) => {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency: 'NGN',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(val);
  };

  const getRoleBadgeStyle = () => {
    if (role === 'Admin') return 'border-[#a78bfa] text-[#a78bfa] bg-[#a78bfa]/10 shadow-[0_0_10px_rgba(167,139,250,0.15)]';
    if (role === 'Analyst') return 'border-[#3b82f6] text-[#3b82f6] bg-[#3b82f6]/10 shadow-[0_0_10px_rgba(59,130,246,0.15)]';
    return 'border-[#C9A84C] text-[#C9A84C] bg-[#C9A84C]/10 shadow-[0_0_10px_rgba(201,168,76,0.15)]';
  };

  return (
    <div className="cyber-bg-radial min-h-screen text-gray-100 flex flex-col font-outfit w-full">
      <AnimatePresence mode="wait">
        {!authToken ? (
          <>
            {currentView !== 'landing' && (
              <div className="fixed top-6 right-6 z-50">
                <button 
                  onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
                  className="p-3 bg-navy-light/45 border border-gray-800 hover:border-gold rounded-xl transition-all shadow-lg backdrop-blur-md"
                  title={theme === 'light' ? "Switch to Dark Mode" : "Switch to Light Mode"}
                >
                  {theme === 'light' ? <Moon className="w-5 h-5 text-slate-700" /> : <Sun className="w-5 h-5 text-gold" />}
                </button>
              </div>
            )}
            {currentView === 'landing' ? (
            // ==========================================
            // PUBLIC LANDING PAGE
            // ==========================================
            <motion.div 
              key="landing"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1 flex flex-col min-h-screen font-outfit"
            >
              {/* Header navbar */}
              <nav className="border-b border-gray-850 bg-navy-dark/40 backdrop-blur-md sticky top-0 z-50">
                <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
                  <div className="flex items-center gap-2.5 cursor-pointer" onClick={() => setCurrentView('landing')}>
                    <div className="p-2 bg-gold/10 rounded-xl border border-gold/20">
                      <Shield className="w-5 h-5 text-gold" />
                    </div>
                    <span className="font-extrabold text-white tracking-tight text-lg">NairaShield AI</span>
                  </div>
                  
                  <div className="hidden md:flex items-center gap-8 text-xs font-semibold uppercase tracking-wider text-gray-400">
                    <a href="#technology" className="hover:text-gold transition-all">Technology</a>
                    <a href="#sandbox" className="hover:text-gold transition-all">Risk Sandbox</a>
                    <a href="#compliance" className="hover:text-gold transition-all">Regulatory Compliance</a>
                  </div>

                  <div className="flex items-center gap-3">
                    <button 
                      onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
                      className="p-2 border border-gray-800 hover:border-gold rounded-lg transition-all"
                      title={theme === 'light' ? "Switch to Dark Mode" : "Switch to Light Mode"}
                    >
                      {theme === 'light' ? <Moon className="w-4 h-4 text-slate-700" /> : <Sun className="w-4 h-4 text-gold" />}
                    </button>
                    <button 
                      onClick={() => {
                        setCurrentView('login');
                        setLoginError('');
                      }}
                      className="px-4 py-2 border border-gold/45 text-gold hover:bg-gold hover:text-navy text-xs font-black rounded-lg uppercase tracking-wider transition-all shadow-[0_0_10px_rgba(201,168,76,0.1)] active:translate-y-px"
                    >
                      Launch Console
                    </button>
                  </div>
                </div>
              </nav>

              {/* Hero Section */}
              <section className="relative overflow-hidden py-20 px-6 flex-1 flex flex-col justify-center">
                <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-gold/5 rounded-full blur-3xl pointer-events-none" />
                <div className="max-w-5xl mx-auto text-center relative z-10 space-y-8">
                  <div className="inline-flex items-center gap-2 px-3.5 py-1.5 bg-emerald-950/20 border border-emerald-900/30 rounded-full text-[10px] font-extrabold uppercase tracking-widest text-emerald-400">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    Operational Security Protocol Active
                  </div>

                  <h1 className="text-4xl sm:text-6xl font-black tracking-tight text-white leading-tight">
                    Shielding Nigerian Financial Rails <br />
                    <span className="bg-gradient-to-r from-gold via-yellow-500 to-amber-600 bg-clip-text text-transparent">with Advanced Anti-Fraud AI</span>
                  </h1>

                  <p className="text-base sm:text-lg text-gray-400 max-w-3xl mx-auto leading-relaxed">
                    Real-time transaction anomaly assessment, local explainability for credit compliance, and automated intercept rules built for high-throughput USSD and NIP rails.
                  </p>

                  <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
                    <button 
                      onClick={() => {
                        setCurrentView('login');
                        setLoginError('');
                      }}
                      className="px-8 py-4 bg-gradient-to-r from-gold to-yellow-600 hover:from-yellow-600 hover:to-gold active:translate-y-px text-navy font-black rounded-xl text-xs uppercase tracking-wider shadow-lg shadow-gold/20 hover:shadow-gold/30 transition-all"
                    >
                      Access Operator Console
                    </button>
                    <a 
                      href="#sandbox"
                      className="px-8 py-4 bg-navy-light/45 border border-gray-800 hover:border-gray-700 active:translate-y-px text-gray-200 font-bold rounded-xl text-xs uppercase tracking-wider transition-all"
                    >
                      Run Threat Sandbox
                    </a>
                  </div>

                  {/* Ticker stats */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-6 pt-16 max-w-4xl mx-auto text-left">
                    <div className="glass-panel p-5 rounded-2xl relative overflow-hidden">
                      <div className="absolute top-0 left-0 right-0 h-0.5 bg-gold/20" />
                      <Database className="w-5 h-5 text-gold/60 mb-2" />
                      <div className="text-2xl font-black text-white">₦4.2B+</div>
                      <div className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Volume Monitored</div>
                    </div>

                    <div className="glass-panel p-5 rounded-2xl relative overflow-hidden">
                      <div className="absolute top-0 left-0 right-0 h-0.5 bg-gold/20" />
                      <Sparkles className="w-5 h-5 text-gold/60 mb-2" />
                      <div className="text-2xl font-black text-white">98.4%</div>
                      <div className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">True Positive Accuracy</div>
                    </div>

                    <div className="glass-panel p-5 rounded-2xl relative overflow-hidden">
                      <div className="absolute top-0 left-0 right-0 h-0.5 bg-gold/20" />
                      <Cpu className="w-5 h-5 text-gold/60 mb-2" />
                      <div className="text-2xl font-black text-white">&lt; 45ms</div>
                      <div className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Evaluation Latency</div>
                    </div>

                    <div className="glass-panel p-5 rounded-2xl relative overflow-hidden">
                      <div className="absolute top-0 left-0 right-0 h-0.5 bg-emerald-500/20" />
                      <Activity className="w-5 h-5 text-emerald-400 mb-2" />
                      <div className="text-2xl font-black text-emerald-400 flex items-center gap-1.5">
                        <span className="w-2 h-2 bg-emerald-400 rounded-full animate-ping" />
                        Live
                      </div>
                      <div className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Pipeline Status</div>
                    </div>
                  </div>
                </div>
              </section>

              {/* Core Features */}
              <section id="technology" className="py-24 px-6 border-t border-gray-900 bg-navy-dark/20">
                <div className="max-w-6xl mx-auto">
                  <div className="text-center mb-16 space-y-3">
                    <span className="text-[10px] font-black uppercase tracking-widest text-gold">Technical Architecture</span>
                    <h2 className="text-3xl font-extrabold text-white">Enterprise-Grade Financial Intelligence</h2>
                    <p className="text-xs text-gray-400 max-w-xl mx-auto">NairaShield integrates high-performance anomaly detection directly into traditional core banking hooks.</p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    <div className="glass-panel p-8 rounded-2xl flex flex-col justify-between glass-panel-hover">
                      <div className="space-y-4">
                        <div className="p-3 bg-gold/10 border border-gold/20 rounded-xl w-fit">
                          <Cpu className="w-6 h-6 text-gold" />
                        </div>
                        <h3 className="text-lg font-bold text-white">Real-Time Ingestion Engine</h3>
                        <p className="text-xs text-gray-400 leading-relaxed">
                          Ingest NIP transfer packets, USSD sequence strings, and card host records directly. Scale amount vectors and evaluate channel codes with native pipeline alignment.
                        </p>
                      </div>
                    </div>

                    <div className="glass-panel p-8 rounded-2xl flex flex-col justify-between glass-panel-hover">
                      <div className="space-y-4">
                        <div className="p-3 bg-gold/10 border border-gold/20 rounded-xl w-fit">
                          <Layers className="w-6 h-6 text-gold" />
                        </div>
                        <h3 className="text-lg font-bold text-white">Local SHAP Explainability</h3>
                        <p className="text-xs text-gray-400 leading-relaxed">
                          Bypasses the "black box" limitations of standard machine learning classifiers. Attribution waterfalls explain feature contributions to risk calculations in log-odds.
                        </p>
                      </div>
                    </div>

                    <div className="glass-panel p-8 rounded-2xl flex flex-col justify-between glass-panel-hover">
                      <div className="space-y-4">
                        <div className="p-3 bg-gold/10 border border-gold/20 rounded-xl w-fit">
                          <Shield className="w-6 h-6 text-gold" />
                        </div>
                        <h3 className="text-lg font-bold text-white">Automated Intercept Hooks</h3>
                        <p className="text-xs text-gray-400 leading-relaxed">
                          Instantly route high-risk predictions to active blockade queues. Medium-risk exceptions are automatically flagged to require hardware OTP authorization.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              {/* Threat Simulator Sandbox */}
              <section id="sandbox" className="py-24 px-6 border-t border-gray-900">
                <div className="max-w-4xl mx-auto">
                  <div className="text-center mb-12 space-y-3">
                    <span className="text-[10px] font-black uppercase tracking-widest text-gold">Live Sandbox Simulator</span>
                    <h2 className="text-3xl font-extrabold text-white">Try the Risk Threshold Sandbox</h2>
                    <p className="text-xs text-gray-400 max-w-lg mx-auto">Simulate live transaction amount limits to see how NairaShield calculates real-time risk scores on the fly.</p>
                  </div>

                  {/* Simulator Box */}
                  <div className="glass-panel p-8 rounded-3xl grid grid-cols-1 md:grid-cols-12 gap-8 items-center">
                    <div className="md:col-span-7 space-y-6">
                      <div>
                        <div className="flex justify-between items-baseline mb-2">
                          <span className="text-xs font-bold text-gray-400 uppercase tracking-wide">Simulation Amount</span>
                          <span className="text-lg font-black text-white font-mono">₦{sandboxAmount.toLocaleString()}</span>
                        </div>
                        <input 
                          type="range"
                          min="10000"
                          max="2500000"
                          step="10000"
                          value={sandboxAmount}
                          onChange={(e) => setSandboxAmount(Number(e.target.value))}
                          className="w-full h-1.5 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-gold focus:outline-none"
                        />
                        <div className="flex justify-between text-[10px] text-gray-500 font-semibold mt-1">
                          <span>₦10K</span>
                          <span>₦1.25M</span>
                          <span>₦2.5M</span>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Presets</span>
                        <div className="flex gap-2.5">
                          <button 
                            onClick={() => setSandboxAmount(150000)}
                            className="px-3 py-1.5 bg-navy-light/60 border border-gray-800 hover:border-gold/40 text-xs font-bold rounded-lg transition-all"
                          >
                            ₦150k USSD
                          </button>
                          <button 
                            onClick={() => setSandboxAmount(850000)}
                            className="px-3 py-1.5 bg-navy-light/60 border border-gray-800 hover:border-gold/40 text-xs font-bold rounded-lg transition-all"
                          >
                            ₦850k POS
                          </button>
                          <button 
                            onClick={() => setSandboxAmount(2200000)}
                            className="px-3 py-1.5 bg-navy-light/60 border border-gray-800 hover:border-gold/40 text-xs font-bold rounded-lg transition-all"
                          >
                            ₦2.2M Transfer
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="md:col-span-5 flex flex-col items-center justify-center p-6 border border-gray-850 bg-navy-dark/40 rounded-2xl relative overflow-hidden text-center">
                      <SVGGauge value={Math.min(0.15 + (sandboxAmount / 2500000.0) * 0.75, 0.98)} />
                      <div className="mt-4 w-full">
                        <div className={`text-[10px] font-black uppercase tracking-widest py-1.5 px-3 rounded-lg border inline-block ${
                          Math.min(0.15 + (sandboxAmount / 2500000.0) * 0.75, 0.98) >= 0.85
                            ? 'border-red-500/20 text-red-400 bg-red-950/15'
                            : Math.min(0.15 + (sandboxAmount / 2500000.0) * 0.75, 0.98) >= 0.50
                            ? 'border-amber-500/20 text-amber-400 bg-amber-950/15'
                            : 'border-emerald-500/20 text-emerald-400 bg-emerald-950/15'
                        }`}>
                          {Math.min(0.15 + (sandboxAmount / 2500000.0) * 0.75, 0.98) >= 0.85 ? 'Intercept & Block' : Math.min(0.15 + (sandboxAmount / 2500000.0) * 0.75, 0.98) >= 0.50 ? 'Require OTP Check' : 'Auto-Approve'}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              {/* Compliance section */}
              <section id="compliance" className="py-16 px-6 border-t border-gray-900 text-center bg-navy-dark/30">
                <div className="max-w-4xl mx-auto glass-panel p-8 rounded-2xl border-emerald-900/10">
                  <div className="flex items-center justify-center gap-2 mb-4 text-emerald-400">
                    <UserCheck className="w-6 h-6" />
                    <span className="text-xs uppercase font-extrabold tracking-widest">Regulatory Integration Compliance</span>
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed max-w-2xl mx-auto">
                    NairaShield matches risk evaluation patterns with the Central Bank of Nigeria's (CBN) Operational Resilience Framework and aligns with Nigeria Data Protection Regulation (NDPR) criteria for secure distributed banking networks.
                  </p>
                </div>
              </section>

              {/* Footer */}
              <footer className="border-t border-gray-900 bg-navy-dark py-8 text-center text-xs text-gray-505">
                <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div>NairaShield AI • System Console v1.1.0 • Made by Benjamin Nweke</div>
                  <div className="flex gap-4">
                    <a href="#" className="hover:text-gold">Operational Guidelines</a>
                    <a href="#" className="hover:text-gold">Security Audits</a>
                  </div>
                </div>
              </footer>
            </motion.div>
          ) : currentView === 'register' ? (
            // ==========================================
            // REGISTRATION PAGE — Premium Full-Featured
            // ==========================================
            <motion.div 
              key="register"
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
              className="flex-1 flex items-center justify-center p-4 min-h-screen py-12"
            >
              <div className="w-full max-w-5xl">
                {/* Page Header */}
                <div className="text-center mb-8">
                  <div className="inline-flex items-center gap-2.5 mb-4">
                    <div className="p-3 bg-gold/10 rounded-2xl border border-gold/20 shadow-[0_0_30px_rgba(201,168,76,0.08)]">
                      <ShieldCheck className="w-8 h-8 text-gold" />
                    </div>
                  </div>
                  <h1 className="text-3xl font-black text-white tracking-tight">Create Your Account</h1>
                  <p className="text-sm text-gray-400 mt-2 max-w-md mx-auto">Join the NairaShield security operations platform. Fill in the details below to register your operator profile.</p>
                </div>

                {/* Progress Steps */}
                <div className="flex items-center justify-center gap-0 mb-10">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-gold text-navy text-xs font-black flex items-center justify-center shadow-[0_0_12px_rgba(201,168,76,0.4)]">1</div>
                    <span className="text-xs font-bold text-gold">Account Details</span>
                  </div>
                  <div className="w-12 h-px bg-gray-700 mx-3" />
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-gray-800 border border-gray-700 text-gray-500 text-xs font-black flex items-center justify-center">2</div>
                    <span className="text-xs font-bold text-gray-500">Access Level</span>
                  </div>
                  <div className="w-12 h-px bg-gray-700 mx-3" />
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-gray-800 border border-gray-700 text-gray-500 text-xs font-black flex items-center justify-center">3</div>
                    <span className="text-xs font-bold text-gray-500">Confirm & Submit</span>
                  </div>
                </div>

                {/* Main Card */}
                <div className="glass-panel rounded-3xl overflow-hidden shadow-2xl relative">
                  {/* Top gold accent bar */}
                  <div className="h-1.5 w-full bg-gradient-to-r from-gold via-yellow-500 to-amber-600" />

                  <div className="grid grid-cols-1 lg:grid-cols-5">
                    {/* ===== LEFT PANEL — Branding & Info ===== */}
                    <div className="lg:col-span-2 bg-gradient-to-br from-[#0a0f1e] via-[#0d1526] to-[#060c18] p-8 flex flex-col justify-between relative border-r border-gray-800/60">
                      <div className="absolute inset-0 pointer-events-none overflow-hidden">
                        <div className="absolute top-0 left-0 w-64 h-64 bg-gold/4 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2" />
                        <div className="absolute bottom-0 right-0 w-48 h-48 bg-blue-600/5 rounded-full blur-3xl translate-x-1/2 translate-y-1/2" />
                      </div>

                      <div className="relative z-10 space-y-8">
                        {/* Brand */}
                        <div className="flex items-center gap-2.5">
                          <div className="p-2 bg-gold/10 rounded-xl border border-gold/20">
                            <Shield className="w-5 h-5 text-gold" />
                          </div>
                          <span className="font-extrabold text-white text-base tracking-tight">NairaShield AI</span>
                        </div>

                        <div>
                          <div className="text-[10px] font-black uppercase tracking-widest text-gold mb-3">Operator Enrollment</div>
                          <h2 className="text-xl font-black text-white leading-snug">Secure Access to Nigeria's Financial Defence Platform</h2>
                          <p className="text-xs text-gray-400 mt-3 leading-relaxed">Gain role-based access to real-time fraud detection, SHAP explainability, and automated intercept controls.</p>
                        </div>

                        {/* Features list */}
                        <div className="space-y-4">
                          {[
                            { icon: <BadgeCheck className="w-4 h-4" />, title: 'Role-Based Access', desc: 'Viewer, Analyst & Admin tiers with scoped permissions' },
                            { icon: <Key className="w-4 h-4" />, title: 'JWT Authentication', desc: 'Cryptographically secure session tokens with auto-refresh' },
                            { icon: <ShieldCheck className="w-4 h-4" />, title: 'Audit Logging', desc: 'Every operator action is timestamped and traceable' },
                          ].map((item, i) => (
                            <div key={i} className="flex gap-3 items-start">
                              <div className="p-1.5 bg-emerald-900/25 border border-emerald-800/30 rounded-lg text-emerald-400 flex-shrink-0 mt-0.5">
                                {item.icon}
                              </div>
                              <div>
                                <div className="text-xs font-bold text-gray-200">{item.title}</div>
                                <div className="text-[10px] text-gray-500 mt-0.5 leading-relaxed">{item.desc}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Footer note */}
                      <div className="relative z-10 mt-8 pt-6 border-t border-gray-800/50">
                        <p className="text-[10px] text-gray-600">System Protocol v1.1.0 • NairaShield AI Console • Made by Benjamin Nweke</p>
                        <p className="text-[10px] text-gray-600 mt-1">CBN-aligned • NDPR compliant</p>
                      </div>
                    </div>

                    {/* ===== RIGHT PANEL — Registration Form ===== */}
                    <div className="lg:col-span-3 p-8 md:p-10 bg-[#080d1a]/50">
                      <div className="mb-7">
                        <h3 className="text-xl font-extrabold text-white">Account Registration</h3>
                        <p className="text-xs text-gray-400 mt-1.5">All fields are required. Passwords must be at least 8 characters.</p>
                      </div>

                      <form onSubmit={handleRegister} className="space-y-5" id="register-form" autoComplete="off">

                        {/* Username field */}
                        <div>
                          <label htmlFor="reg-username" className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">
                            Username
                          </label>
                          <div className="relative">
                            <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">
                              <User className="w-4 h-4" />
                            </div>
                            <input 
                              id="reg-username"
                              type="text" 
                              value={registerUsername}
                              onChange={(e) => setRegisterUsername(e.target.value)}
                              placeholder="e.g. analyst_jones"
                              autoComplete="username"
                              className="w-full bg-[#0d1526] border border-gray-800 focus:border-gold rounded-xl py-3 pl-10 pr-4 text-white placeholder-gray-600 outline-none transition-all focus:ring-2 focus:ring-gold/20 text-sm"
                              required
                              minLength={3}
                            />
                            {registerUsername.length >= 3 && (
                              <div className="absolute right-3.5 top-1/2 -translate-y-1/2 text-emerald-400">
                                <CheckCircle className="w-4 h-4" />
                              </div>
                            )}
                          </div>
                          <p className="text-[10px] text-gray-600 mt-1.5">Minimum 3 characters. Lowercase letters, numbers, and underscores only.</p>
                        </div>

                        {/* Email field */}
                        <div>
                          <label htmlFor="reg-email" className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">
                            Email Address <span className="normal-case font-normal text-gray-500">(optional)</span>
                          </label>
                          <div className="relative">
                            <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">
                              <Mail className="w-4 h-4" />
                            </div>
                            <input 
                              id="reg-email"
                              type="email" 
                              placeholder="operator@institution.gov.ng"
                              autoComplete="email"
                              className="w-full bg-[#0d1526] border border-gray-800 focus:border-gold rounded-xl py-3 pl-10 pr-4 text-white placeholder-gray-600 outline-none transition-all focus:ring-2 focus:ring-gold/20 text-sm"
                            />
                          </div>
                        </div>

                        {/* Password fields row */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div>
                            <label htmlFor="reg-password" className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Password</label>
                            <div className="relative">
                              <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">
                                <Lock className="w-4 h-4" />
                              </div>
                              <input 
                                id="reg-password"
                                type={showRegPassword ? 'text' : 'password'}
                                value={registerPassword}
                                onChange={(e) => setRegisterPassword(e.target.value)}
                                placeholder="Min. 8 characters"
                                autoComplete="new-password"
                                className="w-full bg-[#0d1526] border border-gray-800 focus:border-gold rounded-xl py-3 pl-10 pr-10 text-white placeholder-gray-600 outline-none transition-all focus:ring-2 focus:ring-gold/20 text-sm"
                                required
                                minLength={8}
                              />
                              <button 
                                type="button"
                                onClick={() => setShowRegPassword(p => !p)}
                                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                                tabIndex={-1}
                              >
                                {showRegPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                              </button>
                            </div>
                            {/* Password strength meter */}
                            {registerPassword.length > 0 && (
                              (() => {
                                const len = registerPassword.length;
                                const hasUpper = /[A-Z]/.test(registerPassword);
                                const hasNum = /[0-9]/.test(registerPassword);
                                const hasSpecial = /[^A-Za-z0-9]/.test(registerPassword);
                                const score = (len >= 8 ? 1 : 0) + (len >= 12 ? 1 : 0) + (hasUpper ? 1 : 0) + (hasNum ? 1 : 0) + (hasSpecial ? 1 : 0);
                                const strengthLabel = score <= 1 ? 'Weak' : score === 2 ? 'Fair' : score === 3 ? 'Good' : score === 4 ? 'Strong' : 'Very Strong';
                                const strengthColor = score <= 1 ? '#EF4444' : score === 2 ? '#F59E0B' : score === 3 ? '#EAB308' : score === 4 ? '#22C55E' : '#10B981';
                                const barWidth = `${Math.min((score / 5) * 100, 100)}%`;
                                return (
                                  <div className="mt-2 space-y-1">
                                    <div className="h-1 w-full bg-gray-800 rounded-full overflow-hidden">
                                      <div className="h-full rounded-full transition-all duration-500" style={{ width: barWidth, backgroundColor: strengthColor }} />
                                    </div>
                                    <p className="text-[10px] font-bold" style={{ color: strengthColor }}>{strengthLabel}</p>
                                  </div>
                                );
                              })()
                            )}
                          </div>

                          <div>
                            <label htmlFor="reg-confirm" className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Confirm Password</label>
                            <div className="relative">
                              <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">
                                <Lock className="w-4 h-4" />
                              </div>
                              <input 
                                id="reg-confirm"
                                type={showRegConfirm ? 'text' : 'password'}
                                value={registerConfirmPassword}
                                onChange={(e) => setRegisterConfirmPassword(e.target.value)}
                                placeholder="Re-enter password"
                                autoComplete="new-password"
                                className={`w-full bg-[#0d1526] border rounded-xl py-3 pl-10 pr-10 text-white placeholder-gray-600 outline-none transition-all focus:ring-2 text-sm ${
                                  registerConfirmPassword.length > 0 && registerConfirmPassword !== registerPassword
                                    ? 'border-red-600/60 focus:ring-red-500/20 focus:border-red-500'
                                    : registerConfirmPassword.length > 0 && registerConfirmPassword === registerPassword
                                    ? 'border-emerald-600/60 focus:ring-emerald-500/20 focus:border-emerald-500'
                                    : 'border-gray-800 focus:border-gold focus:ring-gold/20'
                                }`}
                                required
                              />
                              <button 
                                type="button"
                                onClick={() => setShowRegConfirm(p => !p)}
                                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                                tabIndex={-1}
                              >
                                {showRegConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                              </button>
                            </div>
                            {registerConfirmPassword.length > 0 && (
                              <p className={`text-[10px] mt-1.5 font-bold ${
                                registerConfirmPassword === registerPassword ? 'text-emerald-400' : 'text-red-400'
                              }`}>
                                {registerConfirmPassword === registerPassword ? '✓ Passwords match' : '✗ Passwords do not match'}
                              </p>
                            )}
                          </div>
                        </div>

                        {/* Role / Access Level */}
                        <div>
                          <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Access Level</label>
                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            {[
                              { value: 'Viewer', label: 'Viewer', desc: 'Read-only audit access', color: 'gold' },
                              { value: 'Analyst', label: 'Analyst', desc: 'Core anti-fraud controls', color: 'blue' },
                              { value: 'Admin', label: 'Admin', desc: 'Full system configurations', color: 'purple' },
                            ].map(opt => {
                              const isSelected = registerRole === opt.value;
                              const colorMap = {
                                gold: isSelected ? 'border-gold/60 bg-gold/8 text-gold' : 'border-gray-800 text-gray-400 hover:border-gold/30',
                                blue: isSelected ? 'border-blue-500/60 bg-blue-900/15 text-blue-400' : 'border-gray-800 text-gray-400 hover:border-blue-500/30',
                                purple: isSelected ? 'border-purple-500/60 bg-purple-900/15 text-purple-400' : 'border-gray-800 text-gray-400 hover:border-purple-500/30',
                              };
                              return (
                                <button
                                  key={opt.value}
                                  type="button"
                                  onClick={() => setRegisterRole(opt.value)}
                                  className={`p-3 rounded-xl border transition-all text-left ${colorMap[opt.color]}`}
                                >
                                  <div className="font-bold text-xs">{opt.label}</div>
                                  <div className="text-[10px] mt-0.5 opacity-70">{opt.desc}</div>
                                </button>
                              );
                            })}
                          </div>
                          <p className="text-[10px] text-gray-500 mt-2 leading-relaxed">
                            {registerRole === 'Viewer' && '• Read-only. Inspect live transactions, logs, and SHAP attributions.'}
                            {registerRole === 'Analyst' && '• Can flag alerts, request OTP controls, and run fraud predictions.'}
                            {registerRole === 'Admin' && '• Full access: configure risk thresholds and provision new operator accounts.'}
                          </p>
                        </div>

                        {/* Terms */}
                        <div className="rounded-xl border border-gray-800 bg-[#0d1526]/60 p-4">
                          <div className="flex items-start gap-3">
                            <div className="mt-0.5">
                              <input 
                                type="checkbox" 
                                id="accept_terms_v2"
                                checked={acceptTerms}
                                onChange={(e) => setAcceptTerms(e.target.checked)}
                                className="w-4 h-4 cursor-pointer accent-gold"
                                required
                              />
                            </div>
                            <label htmlFor="accept_terms_v2" className="text-xs text-gray-400 leading-relaxed cursor-pointer select-none">
                              I confirm I have security clearance to access this platform and agree to NairaShield's <span className="text-gold font-bold">Operational Protocols</span> and <span className="text-gold font-bold">Audit Logging Policy</span>. All actions within this console are traceable and non-repudiable.
                            </label>
                          </div>
                        </div>

                        {/* Error message */}
                        {loginError && (
                          <motion.div 
                            initial={{ opacity: 0, y: -8 }} 
                            animate={{ opacity: 1, y: 0 }}
                            className="text-red-400 text-xs bg-red-950/20 border border-red-900/40 rounded-xl p-3.5 flex items-center gap-2.5"
                          >
                            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                            <span>{loginError}</span>
                          </motion.div>
                        )}

                        {/* Submit button */}
                        <button 
                          type="submit"
                          disabled={authLoading}
                          className="w-full bg-gradient-to-r from-gold to-yellow-600 hover:from-yellow-500 hover:to-amber-500 active:translate-y-px text-navy font-black py-3.5 rounded-xl flex items-center justify-center gap-2.5 shadow-lg shadow-gold/20 hover:shadow-gold/35 transition-all text-sm uppercase tracking-widest disabled:opacity-60 disabled:cursor-not-allowed"
                        >
                          {authLoading ? (
                            <><RefreshCw className="w-5 h-5 animate-spin" /><span>Creating Account…</span></>
                          ) : (
                            <><ShieldCheck className="w-5 h-5" /><span>Create Account & Access Platform</span><ChevronRight className="w-4 h-4" /></>
                          )}
                        </button>

                        {/* Divider + link */}
                        <div className="flex items-center gap-4">
                          <div className="flex-1 h-px bg-gray-800" />
                          <span className="text-[10px] text-gray-600 font-semibold uppercase tracking-wider">or</span>
                          <div className="flex-1 h-px bg-gray-800" />
                        </div>

                        <div className="flex flex-col items-center gap-2">
                          <button 
                            type="button"
                            onClick={() => { setCurrentView('login'); setLoginError(''); }}
                            className="text-sm text-gray-300 hover:text-gold transition-colors font-semibold"
                          >
                            Already have an account? <span className="text-gold">Sign In</span>
                          </button>
                          <button 
                            type="button"
                            onClick={() => { setCurrentView('landing'); setLoginError(''); }}
                            className="text-[10px] text-gray-600 hover:text-gray-400 font-medium transition-colors"
                          >
                            ← Return to Home Page
                          </button>
                        </div>

                      </form>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          ) : (
            // ==========================================
            // LOGIN PAGE
            // ==========================================
            <motion.div 
              key="login"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="flex-1 flex items-center justify-center p-4 min-h-screen animate-fade-in"
            >
              <div className="glass-panel p-8 rounded-2xl w-full max-w-md shadow-2xl relative overflow-hidden">
                {/* Top Accent line */}
                <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-gold to-yellow-600" />
                
                <div className="flex flex-col items-center mb-8">
                  <div className="p-4 bg-gold/10 rounded-full border border-gold/20 mb-3 shadow-[0_0_20px_rgba(201,168,76,0.1)]">
                    <Shield className="w-12 h-12 text-gold animate-pulse" />
                  </div>
                  <h1 className="text-3xl font-extrabold tracking-tight text-white">NairaShield AI</h1>
                  <p className="text-sm text-gray-400 mt-1">Transaction Integrity & Command Console</p>
                </div>

                <form onSubmit={handleLogin} className="space-y-5">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1.5">Username</label>
                    <div className="relative">
                      <input 
                        type="text" 
                        value={loginUsername}
                        onChange={(e) => setLoginUsername(e.target.value)}
                        placeholder="e.g. analyst"
                        className="w-full bg-navy-dark border border-gray-800 focus:border-gold rounded-lg py-2.5 pl-3 pr-10 text-white placeholder-gray-600 outline-none transition-all focus:ring-1 focus:ring-gold/30 text-xs font-semibold"
                        required
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1.5">Password</label>
                    <div className="relative">
                      <input 
                        type="password" 
                        value={loginPassword}
                        onChange={(e) => setLoginPassword(e.target.value)}
                        placeholder="••••••••"
                        className="w-full bg-navy-dark border border-gray-800 focus:border-gold rounded-lg py-2.5 pl-3 pr-10 text-white placeholder-gray-600 outline-none transition-all focus:ring-1 focus:ring-gold/30 text-xs font-semibold"
                        required
                      />
                      <Lock className="w-5 h-5 text-gray-600 absolute right-3 top-3" />
                    </div>
                  </div>

                  {loginError && (
                    <motion.div 
                      initial={{ opacity: 0, height: 0 }} 
                      animate={{ opacity: 1, height: 'auto' }}
                      className="text-red-400 text-xs bg-red-950/20 border border-red-900/30 rounded p-2.5 flex items-center gap-2"
                    >
                      <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                      <span>{loginError}</span>
                    </motion.div>
                  )}

                  <button 
                    type="submit"
                    disabled={authLoading}
                    className="w-full bg-gradient-to-r from-gold to-yellow-600 hover:from-yellow-600 hover:to-gold active:translate-y-px text-navy font-bold py-3 rounded-lg flex items-center justify-center gap-2 shadow-lg shadow-gold/20 hover:shadow-gold/30 hover:border-gold border border-transparent transition-all text-xs font-bold uppercase tracking-wider"
                  >
                    {authLoading ? (
                      <RefreshCw className="w-5 h-5 animate-spin" />
                    ) : (
                      <span>Access Command Console</span>
                    )}
                  </button>
                </form>

                <div className="mt-4 flex flex-col items-center gap-2">
                  <button 
                    onClick={() => {
                      setCurrentView('register');
                      setLoginError('');
                    }}
                    className="text-xs text-gold hover:underline font-semibold"
                  >
                    Need an account? Sign Up
                  </button>
                  <button 
                    onClick={() => {
                      setCurrentView('landing');
                      setLoginError('');
                    }}
                    className="text-[10px] text-gray-500 hover:text-gray-300 font-semibold"
                  >
                    ← Return to Home Page
                  </button>
                </div>

                {/* Demo Logins */}
                <div className="mt-8 pt-6 border-t border-gray-800/60">
                  <p className="text-center text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Or Login with Demo Role</p>
                  <div className="grid grid-cols-3 gap-2">
                    <button 
                      onClick={() => quickLogin('admin', 'admin123')}
                      className="py-2 text-xs font-bold rounded-lg border border-purple-900/40 bg-purple-950/10 text-purple-400 hover:bg-purple-950/20 transition-all text-center"
                    >
                      Admin
                    </button>
                    <button 
                      onClick={() => quickLogin('analyst', 'analyst123')}
                      className="py-2 text-xs font-bold rounded-lg border border-blue-900/40 bg-blue-950/10 text-blue-400 hover:bg-blue-950/20 transition-all text-center"
                    >
                      Analyst
                    </button>
                    <button 
                      onClick={() => quickLogin('viewer', 'viewer123')}
                      className="py-2 text-xs font-bold rounded-lg border border-gold/30 bg-gold/5 text-gold hover:bg-gold/10 transition-all text-center"
                    >
                      Viewer
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
          </>
        ) : (
          // ==========================================
          // MAIN WEB GUI PORTAL
          // ==========================================
          <motion.div 
            key="dashboard"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex-1 flex flex-col p-4 md:p-6 max-w-7xl mx-auto w-full space-y-6"
          >
            {/* Header section */}
            <header className="flex flex-col sm:flex-row items-center justify-between gap-4 pb-4 border-b border-gray-800/60">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gold/10 rounded-xl border border-gold/20 shadow-inner">
                  <Shield className="w-7 h-7 text-gold" />
                </div>
                <div>
                  <h2 className="text-2xl font-black tracking-tight text-white">NairaShield AI</h2>
                  <p className="text-xs text-gray-400 font-semibold tracking-widest uppercase">Security Command Hub</p>
                </div>
              </div>

              {/* User credentials widget */}
              <div className="flex items-center gap-3">
                <div className="glass-panel py-1.5 pl-3 pr-4 rounded-xl flex items-center gap-3">
                  <div className="text-right">
                    <div className="text-sm font-bold text-white leading-tight">{username}</div>
                    <div className="text-[9px] uppercase tracking-wider font-bold text-emerald-400 flex items-center justify-end gap-1 mt-0.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                      <span>Active</span>
                    </div>
                  </div>
                  <div className={`border rounded-lg text-[10px] font-black uppercase tracking-widest px-2 py-0.5 ${getRoleBadgeStyle()}`}>
                    {role}
                  </div>
                </div>


                <button 
                  onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
                  className="p-2.5 bg-navy-light/45 border border-gray-800 hover:border-gold rounded-xl transition-all"
                  title={theme === 'light' ? "Switch to Dark Mode" : "Switch to Light Mode"}
                >
                  {theme === 'light' ? <Moon className="w-5 h-5 text-slate-700" /> : <Sun className="w-5 h-5 text-gold" />}
                </button>

                <button 
                  onClick={handleLogout}
                  className="p-2.5 bg-red-950/20 border border-red-900/30 hover:border-red-500 rounded-xl text-red-400 hover:bg-red-900/30 transition-all"
                  title="Logout Session"
                >
                  <LogOut className="w-5 h-5" />
                </button>
              </div>
            </header>

            {/* Core Panels Grid */}
            <main className="grid grid-cols-1 lg:grid-template-cols lg:grid-cols-12 gap-6 items-start">
              
              {/* Left Side: Form Controls (span 5) */}
              <div className="lg:col-span-5 space-y-6">
                <section className="glass-panel p-6 rounded-2xl shadow-xl space-y-5">
                  <div className="flex items-center gap-2 border-b border-gray-800/60 pb-3">
                    <Activity className="w-5 h-5 text-gold" />
                    <h3 className="text-lg font-bold text-white">Simulate Transaction</h3>
                  </div>

                  <form onSubmit={handleProfileSubmit} className="space-y-4">
                    {/* Amount */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between items-center text-xs font-bold text-gray-400 uppercase">
                        <label htmlFor="amount-input">Amount (NGN)</label>
                        <span className="text-gold font-extrabold text-sm">{formatNaira(amount)}</span>
                      </div>
                      <input 
                        type="number"
                        id="amount-input"
                        step="any"
                        min="0"
                        max="2500000"
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                        className="w-full bg-navy-dark border border-gray-800 focus:border-gold rounded-lg py-2 pl-3 pr-3 text-white placeholder-gray-600 outline-none transition-all focus:ring-1 focus:ring-gold/30 font-semibold"
                        required
                      />
                      <input 
                        type="range"
                        min="0"
                        max="2500000"
                        step="10000"
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                        className="w-full h-1.5 bg-navy-dark rounded-lg appearance-none cursor-pointer accent-gold mt-2"
                      />
                    </div>

                    {/* Channel Dropdown */}
                    <div className="space-y-1.5">
                      <label htmlFor="channel-select" className="block text-xs font-bold text-gray-400 uppercase">Payment Channel</label>
                      <select 
                        id="channel-select"
                        value={channel} 
                        onChange={(e) => setChannel(e.target.value)}
                        className="w-full bg-navy-dark border border-gray-800 focus:border-gold rounded-lg py-2.5 px-3 text-white outline-none transition-all cursor-pointer font-semibold"
                      >
                        <option value="channel_TRANSFER">Mobile / Wire Transfer</option>
                        <option value="channel_CARD_WEB">Card Checkout (Web)</option>
                        <option value="channel_CARD_HOST">Card Host Transaction</option>
                        <option value="channel_DEBIT">Standard Debit Card</option>
                        <option value="channel_PAYMENT">Over-the-Counter Payment</option>
                        <option value="channel_CASH_OUT">POS Cash Out</option>
                        <option value="channel_CASH_IN">ATM Cash In</option>
                        <option value="channel_CARD_RECURRING">Card Recurring Billing</option>
                        <option value="channel_CARD_PHONE">Card Phone Order</option>
                        <option value="channel_CARD_STORE">Card Store Terminal</option>
                      </select>
                    </div>

                    {/* Registry Pipeline */}
                    <div className="space-y-1.5">
                      <label htmlFor="source-select" className="block text-xs font-bold text-gray-400 uppercase">Validation Registry</label>
                      <select 
                        id="source-select"
                        value={source} 
                        onChange={(e) => setSource(e.target.value)}
                        className="w-full bg-navy-dark border border-gray-800 focus:border-gold rounded-lg py-2.5 px-3 text-white outline-none transition-all cursor-pointer font-semibold"
                      >
                        <option value="source_dataset_PaySim">PaySim Audit Protocol</option>
                        <option value="source_dataset_IEEE-CIS">IEEE-CIS Credit Audit</option>
                      </select>
                    </div>

                    <button 
                      type="submit"
                      disabled={profiling}
                      className="w-full bg-gradient-to-r from-gold to-yellow-600 hover:from-yellow-600 hover:to-gold active:translate-y-px text-navy font-bold py-3 rounded-lg flex items-center justify-center gap-2 shadow-lg shadow-gold/20 hover:shadow-gold/30 transition-all border border-transparent"
                    >
                      {profiling ? (
                        <RefreshCw className="w-5 h-5 animate-spin" />
                      ) : (
                        <>
                          <Send className="w-4 h-4" />
                          <span>Profile Transaction</span>
                        </>
                      )}
                    </button>
                  </form>
                </section>
                {/* Admin Threshold panel */}
                {role === 'Admin' && (
                  <>
                    <section className="glass-panel p-6 rounded-2xl shadow-xl space-y-4">
                      <div className="flex items-center gap-2 border-b border-gray-800/60 pb-3">
                        <Settings className="w-5 h-5 text-purple-400" />
                        <h3 className="text-lg font-bold text-white">Global Sensitivity Overrides</h3>
                      </div>
                      <div className="space-y-3">
                        <div className="flex justify-between items-center text-xs font-bold uppercase">
                          <label htmlFor="threshold-input" className="text-gray-400">Model Fraud Threshold</label>
                          <span className="text-purple-400 font-extrabold text-sm">{threshold.toFixed(2)}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <input 
                            type="range"
                            id="threshold-input"
                            min="0.05"
                            max="0.95"
                            step="0.05"
                            value={threshold}
                            onChange={(e) => setThreshold(parseFloat(e.target.value))}
                            className="flex-1 h-1.5 bg-navy-dark rounded-lg appearance-none cursor-pointer accent-purple-500"
                          />
                          <button 
                            onClick={handleThresholdUpdate}
                            disabled={configLoading}
                            className="bg-purple-650 hover:bg-purple-750 text-white font-semibold py-1.5 px-4 rounded-lg border border-purple-500/20 hover:border-purple-500 transition-all text-xs bg-purple-600"
                          >
                            {configLoading ? 'Saving...' : 'Apply'}
                          </button>
                        </div>
                      </div>
                    </section>

                    <section className="glass-panel p-6 rounded-2xl shadow-xl space-y-4">
                      <div className="flex items-center gap-2 border-b border-gray-800/60 pb-3">
                        <UserCheck className="w-5 h-5 text-purple-400" />
                        <h3 className="text-lg font-bold text-white">User Provisioning Console</h3>
                      </div>
                      <form onSubmit={handleProvisionUser} className="space-y-4">
                        <div className="space-y-1">
                          <label className="block text-xs font-bold text-gray-400 uppercase">Operator Username</label>
                          <input 
                            type="text" 
                            value={provisionUsername}
                            onChange={(e) => setProvisionUsername(e.target.value)}
                            placeholder="e.g. jsmith"
                            className="w-full bg-navy-dark border border-gray-800 focus:border-gold rounded-lg py-2 px-3 text-white placeholder-gray-700 outline-none transition-all focus:ring-1 focus:ring-gold/30 text-xs font-semibold"
                            required
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="block text-xs font-bold text-gray-400 uppercase">Password</label>
                          <input 
                            type="password" 
                            value={provisionPassword}
                            onChange={(e) => setProvisionPassword(e.target.value)}
                            placeholder="••••••••"
                            className="w-full bg-navy-dark border border-gray-800 focus:border-gold rounded-lg py-2 px-3 text-white placeholder-gray-700 outline-none transition-all focus:ring-1 focus:ring-gold/30 text-xs font-semibold"
                            required
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="block text-xs font-bold text-gray-400 uppercase">Operator Role</label>
                          <select 
                            value={provisionRole} 
                            onChange={(e) => setProvisionRole(e.target.value)}
                            className="w-full bg-navy-dark border border-gray-800 focus:border-gold rounded-lg py-2.5 px-3 text-white outline-none transition-all cursor-pointer text-xs font-semibold"
                          >
                            <option value="Viewer">Viewer (Read-only)</option>
                            <option value="Analyst">Analyst (Core Operations)</option>
                            <option value="Admin">Admin (Full Control)</option>
                          </select>
                        </div>
                        <button 
                          type="submit" 
                          disabled={provisionLoading}
                          className="w-full bg-purple-650 hover:bg-purple-750 text-white font-semibold py-2.5 rounded-lg border border-purple-500/20 hover:border-purple-500 transition-all text-xs bg-purple-600"
                        >
                          {provisionLoading ? <RefreshCw className="w-4 h-4 animate-spin mx-auto" /> : 'Provision Account'}
                        </button>
                      </form>
                    </section>
                  </>
                )}
              </div>

              {/* Right Side: Results Display Panel (span 7) */}
              <div className="lg:col-span-7">
                <section className="glass-panel p-6 rounded-2xl shadow-xl min-h-[400px] flex flex-col justify-between">
                  <div className="flex items-center justify-between border-b border-gray-800/60 pb-3 mb-4">
                    <div className="flex items-center gap-2">
                      <Activity className="w-5 h-5 text-gold" />
                      <h3 className="text-lg font-bold text-white">Inference Verdict</h3>
                    </div>
                    {profilingResult && (
                      <span className="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 bg-gray-800 rounded border border-gray-700 text-gray-400">
                        {profilingResult.engine?.split(' ')[0]}
                      </span>
                    )}
                  </div>

                  {!profilingResult ? (
                    // Initial state placeholder
                    <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                      <div className="p-5 bg-gold/5 rounded-full border border-gold/10 mb-4">
                        <Shield className="w-16 h-16 text-gold/30" />
                      </div>
                      <h4 className="text-lg font-bold text-gray-300">Awaiting Simulation</h4>
                      <p className="text-sm text-gray-500 max-w-sm mt-1">Configure and submit the transaction specifications in the simulation panel to initiate model inference scoring.</p>
                    </div>
                  ) : (
                    // Results Details
                    <div className="flex-1 flex flex-col space-y-6">
                      
                      {/* Classification Badge & Gauge Row */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center justify-items-center">
                        <div className="space-y-3 w-full text-center md:text-left">
                          <span className="text-xs uppercase font-extrabold text-gray-500 tracking-wider">Classification Verdict</span>
                          <motion.div 
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            className={`py-3 px-6 rounded-xl border font-black uppercase text-xl tracking-wider text-center shadow-lg ${
                              profilingResult.prediction === 1 
                                ? 'border-red-500/20 text-red-400 bg-red-950/15 shadow-red-950/20' 
                                : 'border-emerald-500/20 text-emerald-400 bg-emerald-950/15 shadow-emerald-950/20'
                            }`}
                          >
                            {profilingResult.prediction === 1 ? 'Blocked / Flagged' : 'Safe / Approved'}
                          </motion.div>
                          <p className="text-xs text-gray-400 font-semibold px-1">
                            {profilingResult.prediction === 1 
                              ? 'This transaction is flagged due to high anomalous patterns. OTP verification or hardware token required.'
                              : 'This transaction exhibits clean behavior signature, well within standard risk threshold bounds.'
                            }
                          </p>
                        </div>
                        
                        <SVGGauge value={profilingResult.fraud_probability} />
                      </div>

                      {/* SHAP Explanation Waterfall Panel */}
                      <div className="border-t border-gray-800/60 pt-5 mt-4">
                        <button 
                          onClick={() => setShowShapDetails(!showShapDetails)}
                          className="w-full flex items-center justify-between text-xs font-bold text-gray-400 uppercase tracking-widest mb-3 hover:text-gold transition-all"
                        >
                          <span>Local SHAP Risk Attribution</span>
                          <div className="flex items-center gap-1">
                            <span>{showShapDetails ? 'Hide' : 'Show'}</span>
                            {showShapDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </div>
                        </button>

                        <AnimatePresence>
                          {showShapDetails && (
                            <motion.div 
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              exit={{ opacity: 0, height: 0 }}
                              className="space-y-2 overflow-hidden"
                            >
                              <div className="text-xs text-gray-500 mb-2 font-semibold">
                                The log-odds impacts indicate how much each feature contributed to pushing the risk score up (+) or down (-).
                              </div>
                              <div className="grid grid-cols-1 gap-2 max-h-[220px] overflow-y-auto pr-1">
                                {Object.entries(profilingResult.explanation?.shap_values || {})
                                  .filter(([_, val]) => val !== 0.0)
                                  .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
                                  .map(([key, val]) => {
                                    const cleanName = key.replace('channel_', 'CHANNEL: ').replace('source_dataset_', 'PIPELINE: ');
                                    return (
                                      <div key={key} className="flex items-center justify-between bg-navy-dark/40 border border-gray-800/40 p-2.5 rounded-lg text-xs">
                                        <span className="font-semibold text-gray-300">{cleanName}</span>
                                        <div className="flex items-center gap-2">
                                          <div className={`w-2 h-2 rounded-full ${val > 0 ? 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.5)]' : 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]'}`} />
                                          <span className={`font-mono font-bold ${val > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                                            {val > 0 ? '+' : ''}{val.toFixed(4)}
                                          </span>
                                        </div>
                                      </div>
                                    );
                                  })
                                }
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>

                    </div>
                  )}
                </section>
              </div>

            </main>


          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
