import React, { useEffect, useState } from 'react';
import { ConfigResponse } from '../types';
import { getConfig, updateConfig, setModel, setVoice } from '../services/apiService';
import * as storage from '../services/storageService';
import { PlusIcon, TrashIcon } from './icons';

interface ConfigPageProps {
  onCancel: () => void;
  onShowAlert: (message: string, title: string) => void;
}

// Helper function to infer provider from model ID
const inferProviderFromModelId = (modelId: string): string => {
  if (modelId.startsWith('gemini')) {
    return 'google';
  } else if (modelId.startsWith('openrouter/')) {
    return 'openrouter';
  } else if (modelId.startsWith('gpt-') || modelId.startsWith('o1-') || modelId.startsWith('o3-')) {
    return 'openai';
  } else {
    return 'ollama';
  }
};

// Consistent styling for form elements
const inputBaseStyle = "px-3 py-2 rounded-md bg-slate-800/50 text-slate-200 border border-slate-600 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-colors";
const buttonAddIconStyle = "p-2 bg-sky-600 hover:bg-sky-700 text-white rounded-md transition-colors disabled:bg-slate-600 disabled:cursor-not-allowed flex-shrink-0";
const buttonRemoveIconStyle = "p-2 text-slate-400 bg-slate-800/40 border border-slate-600/50 hover:bg-red-500/20 hover:text-white rounded-md transition-colors flex-shrink-0";


export const ConfigPage: React.FC<ConfigPageProps> = ({ onCancel, onShowAlert }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [openaiApiKey, setOpenaiApiKey] = useState<string>('');
  const [googleApiKey, setGoogleApiKey] = useState<string>('');
  const [openrouterApiKey, setOpenrouterApiKey] = useState<string>('');
  const [agnoApiKey, setAgnoApiKey] = useState<string>('');
  const [newServer, setNewServer] = useState<{ label: string; url: string }>({ label: '', url: '' });
  const [newModel, setNewModel] = useState<{ label: string; id: string; provider: string }>({ label: '', id: '', provider: 'openai' });
  const [newVoice, setNewVoice] = useState<{ label: string; id: string }>({ label: '', id: '' });
  const [newStdioTool, setNewStdioTool] = useState<{ label: string; command: string }>({ label: '', command: '' });

  const userId = storage.getCurrentUser() || '';

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        setLoading(true);
        const res = await getConfig(userId, controller.signal);
        // Ensure labeled lists exist if only unlabeled lists are present
        // Infer provider from model ID for models without provider metadata
        res.available_models_labeled = (res.available_models_labeled && res.available_models_labeled.length > 0)
          ? res.available_models_labeled.map(m => ({ ...m, provider: m.provider || inferProviderFromModelId(m.id) }))
          : (res.available_models || []).map(id => ({ label: id, id, provider: inferProviderFromModelId(id) }));
        res.available_voices_labeled = (res.available_voices_labeled && res.available_voices_labeled.length > 0) ? res.available_voices_labeled : (res.available_voices || []).map(id => ({ label: id, id }));
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
        openai_api_key: openaiApiKey || undefined,
        google_api_key: googleApiKey || undefined,
        openrouter_api_key: openrouterApiKey || undefined,
        agno_api_key: agnoApiKey || undefined,
        gemini_search_enabled: config.gemini_search_enabled,
        mcp_transport: config.mcp_transport,
        mcp_stdio_commands: config.mcp_stdio_commands || [],
        mcp_stdio_tools: config.mcp_stdio_tools || [],
        available_models: config.available_models || [],
        available_models_labeled: config.available_models_labeled || [],
        available_voices: config.available_voices || [],
        available_voices_labeled: config.available_voices_labeled || [],
        mcp_servers: config.mcp_servers || [],
      };
      const res = await updateConfig(payload);
      setConfig(res);
      try {
        const sessionId = storage.getActiveSessionId();
        if (sessionId) {
          if (res.model) {
            await setModel({ user_id: userId, session_id: sessionId, model: res.model });
          }
          if (res.voice) {
            await setVoice({ user_id: userId, session_id: sessionId, voice: res.voice as any });
          }
        }
        storage.setConfigUpdatedTs(String(Date.now()));
      } catch { }
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

  // --- Synced State Updaters ---

  const updateModelsList = (newLabeledList: Array<{ label: string; id: string; provider?: string }>) => {
    setConfig(prev => {
      if (!prev) return null;
      // Ensure all models have a provider field, infer from ID if missing
      const modelsWithProvider = newLabeledList.map(m => ({
        ...m,
        provider: m.provider || inferProviderFromModelId(m.id)
      }));
      const newUnlabeledList = modelsWithProvider.map(m => m.id);
      return {
        ...prev,
        available_models_labeled: modelsWithProvider,
        available_models: newUnlabeledList
      };
    });
  };

  const updateVoicesList = (newLabeledList: Array<{ label: string; id: string }>) => {
    setConfig(prev => {
      if (!prev) return null;
      const newUnlabeledList = newLabeledList.map(v => v.id);
      return {
        ...prev,
        available_voices_labeled: newLabeledList,
        available_voices: newUnlabeledList
      };
    });
  };

  // --- Handlers ---

  const addModel = () => {
    const id = newModel.id.trim();
    const label = newModel.label.trim() || id;
    const provider = newModel.provider;
    if (!id || !config) return;
    const currentLabeled = config.available_models_labeled || [];
    if (currentLabeled.some(m => m.id === id)) {
      onShowAlert(`Model with ID '${id}' already exists.`, 'Duplicate Model');
      return;
    }
    updateModelsList([...currentLabeled, { label, id, provider }]);
    setNewModel({ label: '', id: '', provider: 'openai' });
  };

  const removeModel = (index: number) => {
    if (!config) return;
    updateModelsList((config.available_models_labeled || []).filter((_, i) => i !== index));
  };

  const updateModel = (index: number, field: 'label' | 'id' | 'provider', value: string) => {
    if (!config) return;
    const newList = (config.available_models_labeled || []).map((m, i) => (i === index ? { ...m, [field]: value } : m));
    updateModelsList(newList);
  };

  const addVoice = () => {
    const id = newVoice.id.trim();
    const label = newVoice.label.trim() || id;
    if (!id || !config) return;
    const currentLabeled = config.available_voices_labeled || [];
    if (currentLabeled.some(v => v.id === id)) {
      onShowAlert(`Voice with ID '${id}' already exists.`, 'Duplicate Voice');
      return;
    }
    updateVoicesList([...currentLabeled, { label, id }]);
    setNewVoice({ label: '', id: '' });
  };

  const removeVoice = (index: number) => {
    if (!config) return;
    updateVoicesList((config.available_voices_labeled || []).filter((_, i) => i !== index));
  };

  const updateVoice = (index: number, field: 'label' | 'id', value: string) => {
    if (!config) return;
    const newList = (config.available_voices_labeled || []).map((v, i) => (i === index ? { ...v, [field]: value } : v));
    updateVoicesList(newList);
  };

  const addServer = () => {
    const label = newServer.label.trim();
    const url = newServer.url.trim();
    if (!url) return;
    setConfig(prev => prev ? { ...prev, mcp_servers: [...(prev.mcp_servers || []), { label: label || 'Server', url }] } : prev);
    setNewServer({ label: '', url: '' });
  };

  const updateServer = (index: number, field: 'label' | 'url', value: string) => {
    setConfig(prev => prev ? {
      ...prev,
      mcp_servers: (prev.mcp_servers || []).map((srv, i) => i === index ? { ...srv, [field]: value } : srv)
    } : prev);
  };

  const removeServer = (index: number) => {
    setConfig(prev => prev ? { ...prev, mcp_servers: (prev.mcp_servers || []).filter((_, i) => i !== index) } : prev);
  };

  const addStdioTool = () => {
    const command = newStdioTool.command.trim();
    const label = newStdioTool.label.trim() || command;
    if (!command) return;
    setConfig(prev => {
      if (!prev) return null;
      const newTools = [...(prev.mcp_stdio_tools || []), { label, command }];
      return { ...prev, mcp_stdio_tools: newTools };
    });
    setNewStdioTool({ label: '', command: '' });
  };

  const updateStdioTool = (index: number, field: 'label' | 'command', value: string) => {
    setConfig(prev => {
      if (!prev) return null;
      const newTools = (prev.mcp_stdio_tools || []).map((tool, i) => i === index ? { ...tool, [field]: value } : tool);
      return { ...prev, mcp_stdio_tools: newTools };
    });
  };

  const removeStdioTool = (index: number) => {
    setConfig(prev => {
      if (!prev) return null;
      const newTools = (prev.mcp_stdio_tools || []).filter((_, i) => i !== index);
      return { ...prev, mcp_stdio_tools: newTools };
    });
  };

  return (
    <div className="flex h-screen w-full font-sans text-white">
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="flex-shrink-0 flex items-center justify-between p-4 bg-slate-900/30 backdrop-blur-md">
          <h1 className="flex items-center gap-3 text-2xl font-bold text-white">
            Configuration
          </h1>
          <div className="flex items-center gap-3">
            <button
              onClick={onCancel}
              className="px-4 py-2 text-sm font-medium text-slate-300 bg-slate-800/40 border border-slate-600/50 hover:bg-white/10 rounded-lg transition-colors"
            >
              Back to Dashboard
            </button>
            <button
              onClick={handleSave}
              disabled={saving || loading || !config}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${saving || loading || !config ? 'bg-slate-700 text-slate-400 cursor-not-allowed' : 'bg-sky-600 hover:bg-sky-700 text-white'}`}
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
              <section className="bg-slate-900/30 backdrop-blur-md border border-slate-500/30 rounded-xl p-6 space-y-6">
                <h2 className="text-xl font-bold">Models & Voice</h2>
                <div>
                  <span className="block text-sm font-medium text-slate-400 mb-2">Available Models</span>
                  <div className="space-y-2">
                    {(config.available_models_labeled || []).map((m, idx) => (
                      <div key={idx} className="flex items-center gap-3">
                        <input type="text" value={m.label} onChange={(e) => updateModel(idx, 'label', e.target.value)} className={`w-40 ${inputBaseStyle}`} />
                        <input type="text" value={m.id} onChange={(e) => updateModel(idx, 'id', e.target.value)} className={`flex-1 ${inputBaseStyle}`} />
                        <select
                          value={m.provider || 'openai'}
                          onChange={(e) => updateModel(idx, 'provider', e.target.value)}
                          className={`w-24 ${inputBaseStyle}`}
                        >
                          <option value="openai">OpenAI</option>
                          <option value="google">Google</option>
                          <option value="openrouter">OpenRouter</option>
                          <option value="ollama">Ollama</option>
                        </select>
                        <button onClick={() => removeModel(idx)} className={buttonRemoveIconStyle} title="Remove Model">
                          <TrashIcon className="w-5 h-5" />
                        </button>
                      </div>
                    ))}
                    <div className="flex items-center gap-3 pt-2">
                      <input type="text" value={newModel.label} onChange={(e) => setNewModel(prev => ({ ...prev, label: e.target.value }))} placeholder="Label" className={`w-40 ${inputBaseStyle}`} />
                      <input type="text" value={newModel.id} onChange={(e) => setNewModel(prev => ({ ...prev, id: e.target.value }))} placeholder="Model id" className={`flex-1 ${inputBaseStyle}`} />
                      <select
                        value={newModel.provider}
                        onChange={(e) => setNewModel(prev => ({ ...prev, provider: e.target.value }))}
                        className={`w-24 ${inputBaseStyle}`}
                      >
                        <option value="openai">OpenAI</option>
                        <option value="google">Google</option>
                        <option value="openrouter">OpenRouter</option>
                        <option value="ollama">Ollama</option>
                      </select>
                      <button onClick={addModel} className={buttonAddIconStyle} title="Add Model">
                        <PlusIcon className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>
                <div>
                  <span className="block text-sm font-medium text-slate-400 mb-2">Available Voices</span>
                  <div className="space-y-2">
                    {(config.available_voices_labeled || []).map((v, idx) => (
                      <div key={idx} className="flex items-center gap-3">
                        <input type="text" value={v.label} onChange={(e) => updateVoice(idx, 'label', e.target.value)} className={`w-40 ${inputBaseStyle}`} />
                        <input type="text" value={v.id} onChange={(e) => updateVoice(idx, 'id', e.target.value)} className={`flex-1 ${inputBaseStyle}`} />
                        <button onClick={() => removeVoice(idx)} className={buttonRemoveIconStyle} title="Remove Voice">
                          <TrashIcon className="w-5 h-5" />
                        </button>
                      </div>
                    ))}
                    <div className="flex items-center gap-3 pt-2">
                      <input type="text" value={newVoice.label} onChange={(e) => setNewVoice(prev => ({ ...prev, label: e.target.value }))} placeholder="Label" className={`w-40 ${inputBaseStyle}`} />
                      <input type="text" value={newVoice.id} onChange={(e) => setNewVoice(prev => ({ ...prev, id: e.target.value }))} placeholder="Voice id" className={`flex-1 ${inputBaseStyle}`} />
                      <button onClick={addVoice} className={buttonAddIconStyle} title="Add Voice">
                        <PlusIcon className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>
                <label className="block">
                  <span className="block text-sm font-medium text-slate-400 mb-2">AI Base URL</span>
                  <input type="text" value={config.ollama_base_url} onChange={(e) => updateField('ollama_base_url', e.target.value)} placeholder="http://localhost:11434" className={`w-full ${inputBaseStyle}`} />
                </label>
                <label className="block">
                  <span className="block text-sm font-medium text-slate-400 mb-2">OpenAI API Key (optional)</span>
                  <input
                    type="password"
                    value={openaiApiKey}
                    onChange={(e) => setOpenaiApiKey(e.target.value)}
                    placeholder={config.openai_api_key_set ? 'Key is set (enter to replace)' : 'sk-... or any string'}
                    className={`w-full ${inputBaseStyle}`}
                  />
                  <p className="mt-2 text-xs text-slate-500">Stored in memory; never displayed back.</p>
                </label>
                <label className="block">
                  <span className="block text-sm font-medium text-slate-400 mb-2">Google API Key (optional)</span>
                  <input
                    type="password"
                    value={googleApiKey}
                    onChange={(e) => setGoogleApiKey(e.target.value)}
                    placeholder={config.google_api_key_set ? 'Key is set (enter to replace)' : 'AIza...'}
                    className={`w-full ${inputBaseStyle}`}
                  />
                  <p className="mt-2 text-xs text-slate-500">Stored in memory; never displayed back.</p>
                </label>
                <label className="block">
                  <span className="block text-sm font-medium text-slate-400 mb-2">OpenRouter API Key (optional)</span>
                  <input
                    type="password"
                    value={openrouterApiKey}
                    onChange={(e) => setOpenrouterApiKey(e.target.value)}
                    placeholder={config.openrouter_api_key_set ? 'Key is set (enter to replace)' : 'sk-or-...'}
                    className={`w-full ${inputBaseStyle}`}
                  />
                  <p className="mt-2 text-xs text-slate-500">Stored in memory; never displayed back.</p>
                </label>
                <label className="block">
                  <span className="block text-sm font-medium text-slate-400 mb-2">AGNO API Key (optional)</span>
                  <input
                    type="password"
                    value={agnoApiKey}
                    onChange={(e) => setAgnoApiKey(e.target.value)}
                    placeholder={config.agno_api_key_set ? 'Key is set (enter to replace)' : 'Enter AGNO API key for monitoring'}
                    className={`w-full ${inputBaseStyle}`}
                  />
                  <p className="mt-2 text-xs text-slate-500">For agent monitoring at https://app.agno.com/</p>
                </label>
                <label className="flex items-center gap-3 p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
                  <input
                    type="checkbox"
                    checked={config.gemini_search_enabled}
                    onChange={(e) => updateField('gemini_search_enabled', e.target.checked)}
                    className="w-5 h-5 rounded border-slate-600 text-sky-600 focus:ring-sky-500 bg-slate-700"
                  />
                  <div>
                    <span className="block text-sm font-medium text-slate-200">Enable Gemini Search</span>
                    <span className="block text-xs text-slate-400">Allows Gemini models to use Google Search tool</span>
                  </div>
                </label>
              </section>

              {/* MCP Settings Card */}
              <section className="bg-slate-900/30 backdrop-blur-md border border-slate-500/30 rounded-xl p-6 space-y-6">
                <h2 className="text-xl font-bold">MCP Settings</h2>
                <label className="block">
                  <span className="block text-sm font-medium text-slate-400 mb-2">Transport</span>
                  <select value={config.mcp_transport} onChange={(e) => updateField('mcp_transport', e.target.value)} className={`w-full ${inputBaseStyle}`} >
                    <option value="streamable-http">streamable-http</option>
                    <option value="stdio">stdio</option>
                  </select>
                </label>
                {config.mcp_transport === 'streamable-http' && (
                  <div className="space-y-4">
                    <span className="block text-sm font-medium text-slate-400">MCP Servers</span>
                    <div className="space-y-2">
                      {(config.mcp_servers || []).map((srv, idx) => (
                        <div key={idx} className="flex items-center gap-3">
                          <input type="text" value={srv.label} onChange={(e) => updateServer(idx, 'label', e.target.value)} className={`w-40 ${inputBaseStyle}`} />
                          <input type="text" value={srv.url} onChange={(e) => updateServer(idx, 'url', e.target.value)} className={`flex-1 ${inputBaseStyle}`} />
                          <button onClick={() => removeServer(idx)} className={buttonRemoveIconStyle} title="Remove Server">
                            <TrashIcon className="w-5 h-5" />
                          </button>
                        </div>
                      ))}
                    </div>
                    <div className="flex items-center gap-3 pt-2">
                      <input type="text" value={newServer.label} onChange={(e) => setNewServer(prev => ({ ...prev, label: e.target.value }))} placeholder="Label" className={`w-40 ${inputBaseStyle}`} />
                      <input type="text" value={newServer.url} onChange={(e) => setNewServer(prev => ({ ...prev, url: e.target.value }))} placeholder="https://..." className={`flex-1 ${inputBaseStyle}`} />
                      <button onClick={addServer} className={buttonAddIconStyle} title="Add Server">
                        <PlusIcon className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                )}
                {config.mcp_transport === 'stdio' && (
                  <div className="space-y-4">
                    <div>
                      <span className="block text-sm font-medium text-slate-400 mb-2">Stdio Tools</span>
                      <div className="space-y-2">
                        {(config.mcp_stdio_tools || []).map((tool, idx) => (
                          <div key={idx} className="flex items-center gap-3">
                            <input type="text" value={tool.label} onChange={(e) => updateStdioTool(idx, 'label', e.target.value)} className={`w-40 ${inputBaseStyle}`} />
                            <input type="text" value={tool.command} onChange={(e) => updateStdioTool(idx, 'command', e.target.value)} className={`flex-1 ${inputBaseStyle}`} />
                            <button onClick={() => removeStdioTool(idx)} className={buttonRemoveIconStyle} title="Remove Tool">
                              <TrashIcon className="w-5 h-5" />
                            </button>
                          </div>
                        ))}
                        <div className="flex items-center gap-3 pt-2">
                          <input type="text" value={newStdioTool.label} onChange={(e) => setNewStdioTool(prev => ({ ...prev, label: e.target.value }))} placeholder="Label" className={`w-40 ${inputBaseStyle}`} />
                          <input type="text" value={newStdioTool.command} onChange={(e) => setNewStdioTool(prev => ({ ...prev, command: e.target.value }))} placeholder="npx -y @..." className={`flex-1 ${inputBaseStyle}`} />
                          <button onClick={addStdioTool} className={buttonAddIconStyle} title="Add Tool">
                            <PlusIcon className="w-5 h-5" />
                          </button>
                        </div>
                        <p className="mt-2 text-xs text-slate-500">Commands run via stdio (e.g., npx/uvx). They will be connected alongside HTTP MCP servers.</p>
                      </div>
                    </div>
                  </div>
                )}
              </section>
            </div>
          ) : (
            <div className="p-8 text-center text-slate-400">No configuration loaded.</div>
          )}
        </main>
      </div>
    </div>
  );
};
