import React, { useEffect, useState } from 'react';
import { ConfigResponse } from '../types';
import { getConfig, updateConfig } from '../services/apiService';
import * as storage from '../services/storageService';
import { PlusIcon, TrashIcon } from './icons';

interface ConfigPageProps {
  onCancel: () => void;
  onShowAlert: (message: string, title: string) => void;
}

// Consistent styling for form elements
const inputBaseStyle = "w-full px-3 py-2 rounded-md bg-slate-900 text-gray-200 border-2 border-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-colors";
const buttonAddIconStyle = "p-2 bg-sky-600 hover:bg-sky-700 text-white rounded-md transition-colors disabled:bg-slate-600 disabled:cursor-not-allowed flex-shrink-0";
const buttonRemoveIconStyle = "p-2 text-gray-400 bg-slate-700 hover:bg-red-600 hover:text-white rounded-md transition-colors flex-shrink-0";
// Read-only input style that supports easy full selection
const readOnlyInputStyle = `${inputBaseStyle} font-mono text-sm truncate cursor-text`;


export const ConfigPage: React.FC<ConfigPageProps> = ({ onCancel, onShowAlert }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [newServer, setNewServer] = useState<{ label: string; url: string }>({ label: '', url: '' });
  const [newModel, setNewModel] = useState<string>('');
  const [newVoice, setNewVoice] = useState<string>('');

  const userId = storage.getCurrentUser() || '';

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        setLoading(true);
        const res = await getConfig(userId, controller.signal);
        setConfig(res);
        setError(null);
      } catch (err: any) {
        console.error('Failed to load config:', err);
        setError('Failed to load configuration.');
      } finally {
        setLoading(false);
      }
    };
    load();
    return () => controller.abort();
  }, [userId]);

  const handleSave = async () => {
    if (!config) return;
    try {
      setSaving(true);
      const payload = {
        user_id: userId,
        model: config.model,
        voice: config.voice,
        ollama_base_url: config.ollama_base_url,
        mcp_transport: config.mcp_transport,
        mcp_stdio_command: config.mcp_stdio_command ?? null,
        mcp_stdio_args: config.mcp_stdio_args || [],
        available_models: config.available_models || [],
        available_voices: (config as any).available_voices || [],
        mcp_servers: config.mcp_servers || [],
      };
      const res = await updateConfig(payload);
      setConfig(res);
      onShowAlert('Configuration saved successfully.', 'Success');
    } catch (err: any) {
      console.error('Failed to save config:', err);
      onShowAlert('Failed to save configuration.', 'Error');
    } finally {
      setSaving(false);
    }
  };

  const updateField = (field: keyof ConfigResponse, value: any) => {
    setConfig(prev => prev ? { ...prev, [field]: value } : prev);
  };

  // Voice options now managed via available_voices in runtime config

  const addServer = () => {
    const label = newServer.label.trim();
    const url = newServer.url.trim();
    if (!url) return;
    setConfig(prev => prev ? { ...prev, mcp_servers: [...(prev.mcp_servers || []), { label: label || 'Server', url }] } : prev);
    setNewServer({ label: '', url: '' });
  };

  const removeServer = (index: number) => {
    setConfig(prev => prev ? { ...prev, mcp_servers: (prev.mcp_servers || []).filter((_, i) => i !== index) } : prev);
  };
  
  const addModel = () => {
    const model = newModel.trim();
    if (!model) return;
    setConfig(prev => prev ? { ...prev, available_models: Array.from(new Set([...(prev.available_models || []), model])) } : prev);
    setNewModel('');
  };

  const removeModel = (index: number) => {
    setConfig(prev => prev ? { ...prev, available_models: (prev.available_models || []).filter((_, i) => i !== index) } : prev);
  };

  const addVoice = () => {
    const voice = newVoice.trim();
    if (!voice) return;
    setConfig(prev => prev ? { ...prev, available_voices: Array.from(new Set([...(prev.available_voices || []), voice])) } : prev);
    setNewVoice('');
  };

  const removeVoice = (index: number) => {
    setConfig(prev => prev ? { ...prev, available_voices: (prev.available_voices || []).filter((_, i) => i !== index) } : prev);
  };

  return (
    <div className="flex h-screen w-full font-sans bg-gradient-to-br from-gray-900 to-gray-800 text-white">
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="flex-shrink-0 flex items-center justify-between p-4 bg-gray-900/50 border-b border-slate-700">
          <h1 className="flex items-center gap-3 text-2xl font-bold text-white">
            Configuration
          </h1>
          <div className="flex items-center gap-3">
            <button
              onClick={onCancel}
              className="px-4 py-2 text-sm font-medium text-gray-300 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
            >
              Back to Dashboard
            </button>
            <button
              onClick={handleSave}
              disabled={saving || loading || !config}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${saving || loading || !config ? 'bg-slate-700 text-gray-400 cursor-not-allowed' : 'bg-sky-600 hover:bg-sky-700 text-white'}`}
            >
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6 lg:p-8 space-y-8">
          {error && (
            <div className="p-4 bg-red-900/40 border border-red-800 text-red-200 rounded-lg">{error}</div>
          )}
          {loading ? (
            <div className="flex items-center justify-center h-full">
                <div className="w-8 h-8 border-2 border-t-sky-400 border-r-sky-400 border-b-sky-400 border-l-transparent rounded-full animate-spin"></div>
            </div>
          ) : config ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Models & Voice Card */}
              <section className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 space-y-6">
                <h2 className="text-xl font-bold">Models & Voice</h2>
                <div>
                  <span className="block text-sm font-medium text-gray-400 mb-2">Available Models</span>
                  <div className="space-y-2">
                    {(config.available_models || []).map((m, idx) => (
                      <div key={`${m}-${idx}`} className="flex items-center gap-3">
                        <input
                          type="text"
                          readOnly
                          value={m}
                          className={readOnlyInputStyle}
                          onFocus={(e) => e.currentTarget.select()}
                          onMouseUp={(e) => e.preventDefault()} // keep selection
                        />
                        <button onClick={() => removeModel(idx)} className={buttonRemoveIconStyle} title="Remove Model">
                            <TrashIcon className="w-5 h-5" />
                        </button>
                      </div>
                    ))}
                    <div className="flex items-center gap-3 pt-2">
                      <input type="text" value={newModel} onChange={(e) => setNewModel(e.target.value)} placeholder="Add new model id" className={`flex-1 ${inputBaseStyle}`} />
                      <button onClick={addModel} className={buttonAddIconStyle} title="Add Model">
                          <PlusIcon className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>
                <div>
                  <span className="block text-sm font-medium text-gray-400 mb-2">Available Voices</span>
                  <div className="space-y-2">
                    {(config.available_voices || []).map((v, idx) => (
                      <div key={`${v}-${idx}`} className="flex items-center gap-3">
                        <input
                          type="text"
                          readOnly
                          value={v}
                          className={readOnlyInputStyle}
                          onFocus={(e) => e.currentTarget.select()}
                          onMouseUp={(e) => e.preventDefault()}
                        />
                        <button onClick={() => removeVoice(idx)} className={buttonRemoveIconStyle} title="Remove Voice">
                            <TrashIcon className="w-5 h-5" />
                        </button>
                      </div>
                    ))}
                    <div className="flex items-center gap-3 pt-2">
                      <input type="text" value={newVoice} onChange={(e) => setNewVoice(e.target.value)} placeholder="Add new voice id" className={`flex-1 ${inputBaseStyle}`} onFocus={(e) => e.currentTarget.select()} onMouseUp={(e) => e.preventDefault()} />
                      <button onClick={addVoice} className={buttonAddIconStyle} title="Add Voice">
                          <PlusIcon className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>
                <label className="block">
                  <span className="block text-sm font-medium text-gray-400 mb-2">Ollama Base URL</span>
                  <input type="text" value={config.ollama_base_url} onChange={(e) => updateField('ollama_base_url', e.target.value)} placeholder="http://localhost:11434" className={inputBaseStyle} onFocus={(e) => e.currentTarget.select()} onMouseUp={(e) => e.preventDefault()} />
                </label>
              </section>

              {/* MCP Settings Card */}
              <section className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 space-y-6">
                <h2 className="text-xl font-bold">MCP Settings</h2>
                <label className="block">
                  <span className="block text-sm font-medium text-gray-400 mb-2">Transport</span>
                  <select value={config.mcp_transport} onChange={(e) => updateField('mcp_transport', e.target.value)} className={inputBaseStyle} >
                    <option value="streamable-http">streamable-http</option>
                    <option value="stdio">stdio</option>
                  </select>
                </label>
                {config.mcp_transport === 'streamable-http' && (
                  <div className="space-y-4">
                    <span className="block text-sm font-medium text-gray-400">MCP Servers</span>
                    <div className="space-y-2">
                        {(config.mcp_servers || []).map((srv, idx) => (
                        <div key={`${srv.url}-${idx}`} className="flex items-center gap-3">
                            <input
                              type="text"
                              readOnly
                              value={srv.label}
                              className={`w-40 ${readOnlyInputStyle}`}
                              onFocus={(e) => e.currentTarget.select()}
                              onMouseUp={(e) => e.preventDefault()}
                            />
                            <input
                              type="text"
                              readOnly
                              value={srv.url}
                              className={readOnlyInputStyle}
                              onFocus={(e) => e.currentTarget.select()}
                              onMouseUp={(e) => e.preventDefault()}
                            />
                            <button onClick={() => removeServer(idx)} className={buttonRemoveIconStyle} title="Remove Server">
                                <TrashIcon className="w-5 h-5" />
                            </button>
                        </div>
                        ))}
                    </div>
                    <div className="flex items-center gap-3 pt-2">
                      <input type="text" value={newServer.label} onChange={(e) => setNewServer(prev => ({ ...prev, label: e.target.value }))} placeholder="Label" className={`w-40 ${inputBaseStyle}`} onFocus={(e) => e.currentTarget.select()} onMouseUp={(e) => e.preventDefault()} />
                      <input type="text" value={newServer.url} onChange={(e) => setNewServer(prev => ({ ...prev, url: e.target.value }))} placeholder="https://..." className={`flex-1 ${inputBaseStyle}`} onFocus={(e) => e.currentTarget.select()} onMouseUp={(e) => e.preventDefault()} />
                      <button onClick={addServer} className={buttonAddIconStyle} title="Add Server">
                          <PlusIcon className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                )}
                {config.mcp_transport === 'stdio' && (
                  <div className="space-y-4">
                    <label className="block">
                      <span className="block text-sm font-medium text-gray-400 mb-2">Stdio Command</span>
                      <input type="text" value={config.mcp_stdio_command || ''} onChange={(e) => updateField('mcp_stdio_command', e.target.value)} placeholder="python" className={inputBaseStyle} onFocus={(e) => e.currentTarget.select()} onMouseUp={(e) => e.preventDefault()} />
                    </label>
                    <label className="block">
                      <span className="block text-sm font-medium text-gray-400 mb-2">Stdio Args (comma-separated)</span>
                      <input type="text" value={(config.mcp_stdio_args || []).join(', ')} onChange={(e) => updateField('mcp_stdio_args', e.target.value.split(',').map(s => s.trim()).filter(Boolean))} placeholder="script.py, --flag" className={inputBaseStyle} onFocus={(e) => e.currentTarget.select()} onMouseUp={(e) => e.preventDefault()} />
                    </label>
                  </div>
                )}
              </section>
            </div>
          ) : (
            <div className="p-8 text-center text-gray-400">No configuration loaded.</div>
          )}
        </main>
      </div>
    </div>
  );
};