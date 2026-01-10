import React, { useEffect, useState } from 'react';
import { ConfigResponse } from '../types';
import { getConfig, updateConfig, setModel, setVoice } from '../services/apiService';
import * as storage from '../services/storageService';
import { PlusIcon, TrashIcon, ImageIcon, VideoIcon, MicIcon, KeyIcon, GlobeIcon, ServerIcon, TerminalIcon, SearchIcon, CheckIcon } from './icons';
import { CustomDropdown } from './CustomDropdown';

interface ConfigPageProps {
  onCancel: () => void;
  onShowAlert: (message: string, title: string) => void;
  onShowConfirmation: (title: string, message: string, onConfirm: () => void) => void;
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


export const ConfigPage: React.FC<ConfigPageProps> = ({ onCancel, onShowAlert, onShowConfirmation }) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [openaiApiKey, setOpenaiApiKey] = useState<string>('');
  const [googleApiKey, setGoogleApiKey] = useState<string>('');
  const [openrouterApiKey, setOpenrouterApiKey] = useState<string>('');
  const [agnoApiKey, setAgnoApiKey] = useState<string>('');
  const [newServer, setNewServer] = useState<{ label: string; url: string }>({ label: '', url: '' });
  const [newModel, setNewModel] = useState<{ label: string; id: string; provider: string }>({ label: '', id: '', provider: 'ollama' });
  const [newVoice, setNewVoice] = useState<{ label: string; id: string }>({ label: '', id: '' });
  const [newStdioTool, setNewStdioTool] = useState<{ label: string; command: string }>({ label: '', command: '' });
  const [selectedModelProvider, setSelectedModelProvider] = useState<string>('all');

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
        openai_base_url: config.openai_base_url,
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
    const model = (config.available_models_labeled || [])[index];
    onShowConfirmation(
      'Delete Model',
      `Are you sure you want to delete "${model?.label || model?.id}"?`,
      () => updateModelsList((config.available_models_labeled || []).filter((_, i) => i !== index))
    );
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
    const voice = (config.available_voices_labeled || [])[index];
    onShowConfirmation(
      'Delete Voice',
      `Are you sure you want to delete "${voice?.label || voice?.id}"?`,
      () => updateVoicesList((config.available_voices_labeled || []).filter((_, i) => i !== index))
    );
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
    const server = config?.mcp_servers?.[index];
    onShowConfirmation(
      'Delete Server',
      `Are you sure you want to delete "${server?.label || server?.url}"?`,
      () => setConfig(prev => prev ? { ...prev, mcp_servers: (prev.mcp_servers || []).filter((_, i) => i !== index) } : prev)
    );
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
    const tool = config?.mcp_stdio_tools?.[index];
    onShowConfirmation(
      'Delete Tool',
      `Are you sure you want to delete "${tool?.label || tool?.command}"?`,
      () => setConfig(prev => {
        if (!prev) return null;
        const newTools = (prev.mcp_stdio_tools || []).filter((_, i) => i !== index);
        return { ...prev, mcp_stdio_tools: newTools };
      })
    );
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
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium text-slate-400">Available Models</span>
                    <span className="text-xs text-slate-500">{(config.available_models_labeled || []).length} models</span>
                  </div>

                  {/* Provider Filter Tabs */}
                  {(() => {
                    const models = config.available_models_labeled || [];
                    const providers = ['all', ...Array.from(new Set(models.map(m => m.provider || 'ollama')))];
                    const providerCounts = providers.reduce((acc, p) => {
                      acc[p] = p === 'all' ? models.length : models.filter(m => (m.provider || 'ollama') === p).length;
                      return acc;
                    }, {} as Record<string, number>);

                    return (
                      <div className="flex flex-wrap gap-1 mb-3 border-b border-slate-700/50 pb-2">
                        {providers.map(provider => (
                          <button
                            key={provider}
                            onClick={() => setSelectedModelProvider(provider)}
                            className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all capitalize ${selectedModelProvider === provider
                              ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                              : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/50 border border-transparent'
                              }`}
                          >
                            {provider} <span className="text-slate-600 ml-1">({providerCounts[provider]})</span>
                          </button>
                        ))}
                      </div>
                    );
                  })()}

                  {/* Filtered Model List */}
                  <div className="space-y-2 max-h-[320px] overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700">
                    {(config.available_models_labeled || [])
                      .filter(m => selectedModelProvider === 'all' || (m.provider || 'ollama') === selectedModelProvider)
                      .map((m) => {
                        const idx = (config.available_models_labeled || []).findIndex(model => model.id === m.id);
                        return (
                          <div key={m.id} className="group flex items-center gap-3 bg-slate-800/40 border border-slate-700/50 rounded-lg p-2.5 hover:border-sky-500/30 transition-all">
                            {/* Model Info */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <input
                                  type="text"
                                  value={m.label}
                                  onChange={(e) => updateModel(idx, 'label', e.target.value)}
                                  className="bg-transparent border-none p-0 text-sm font-semibold text-slate-200 placeholder-slate-600 focus:ring-0 w-auto max-w-[160px]"
                                  placeholder="Model Name"
                                />
                                <span className="text-slate-600">·</span>
                                <input
                                  type="text"
                                  value={m.id}
                                  onChange={(e) => updateModel(idx, 'id', e.target.value)}
                                  className="flex-1 bg-transparent border-none p-0 text-xs font-mono text-slate-500 focus:text-sky-400 focus:ring-0 transition-colors truncate"
                                  placeholder="model-id"
                                />
                              </div>
                            </div>

                            {/* Capabilities - Compact Icon Toggles */}
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                onClick={() => {
                                  if (!config) return;
                                  const newList = (config.available_models_labeled || []).map((model, i) =>
                                    i === idx ? { ...model, supports_images: !model.supports_images } : model
                                  );
                                  updateModelsList(newList);
                                }}
                                className={`p-1.5 rounded transition-all ${m.supports_images ? 'bg-sky-500/20 text-sky-400' : 'bg-slate-800/50 text-slate-600 hover:text-slate-400'}`}
                                title="Image Support"
                              >
                                <ImageIcon className="w-3.5 h-3.5" />
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  if (!config) return;
                                  const newList = (config.available_models_labeled || []).map((model, i) =>
                                    i === idx ? { ...model, supports_audio: !model.supports_audio } : model
                                  );
                                  updateModelsList(newList);
                                }}
                                className={`p-1.5 rounded transition-all ${m.supports_audio ? 'bg-purple-500/20 text-purple-400' : 'bg-slate-800/50 text-slate-600 hover:text-slate-400'}`}
                                title="Audio Support"
                              >
                                <MicIcon className="w-3.5 h-3.5" />
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  if (!config) return;
                                  const newList = (config.available_models_labeled || []).map((model, i) =>
                                    i === idx ? { ...model, supports_videos: !model.supports_videos } : model
                                  );
                                  updateModelsList(newList);
                                }}
                                className={`p-1.5 rounded transition-all ${m.supports_videos ? 'bg-pink-500/20 text-pink-400' : 'bg-slate-800/50 text-slate-600 hover:text-slate-400'}`}
                                title="Video Support"
                              >
                                <VideoIcon className="w-3.5 h-3.5" />
                              </button>
                            </div>

                            {/* Provider Badge */}
                            <span className={`text-[10px] font-medium px-2 py-0.5 rounded capitalize ${m.provider === 'openai' ? 'bg-emerald-500/10 text-emerald-400' :
                              m.provider === 'google' ? 'bg-blue-500/10 text-blue-400' :
                                m.provider === 'openrouter' ? 'bg-orange-500/10 text-orange-400' :
                                  'bg-slate-700/50 text-slate-400'
                              }`}>
                              {m.provider || 'ollama'}
                            </span>

                            {/* Delete Button */}
                            <button
                              onClick={() => removeModel(idx)}
                              className="p-1.5 rounded text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-colors opacity-0 group-hover:opacity-100"
                              title="Remove Model"
                            >
                              <TrashIcon className="w-4 h-4" />
                            </button>
                          </div>
                        );
                      })}
                  </div>

                  {/* Add New Model - Compact Row */}
                  <div className="flex items-center gap-2 border border-dashed border-slate-700/50 rounded-lg p-2 mt-3 hover:border-sky-500/40 transition-all">
                    <input
                      type="text"
                      value={newModel.label}
                      onChange={(e) => setNewModel(prev => ({ ...prev, label: e.target.value }))}
                      placeholder="Name"
                      className="w-24 bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:ring-1 focus:ring-sky-500 focus:border-sky-500"
                    />
                    <input
                      type="text"
                      value={newModel.id}
                      onChange={(e) => setNewModel(prev => ({ ...prev, id: e.target.value }))}
                      placeholder="Model ID (e.g. gpt-4o)"
                      className="flex-1 bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:ring-1 focus:ring-sky-500 focus:border-sky-500 font-mono"
                    />
                    <div className="w-24">
                      <CustomDropdown
                        options={['ollama', 'openai', 'google', 'openrouter']}
                        value={newModel.provider}
                        onChange={(val) => setNewModel(prev => ({ ...prev, provider: val }))}
                      />
                    </div>
                    <button
                      onClick={addModel}
                      disabled={!newModel.id.trim()}
                      className="p-1.5 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded transition-colors"
                      title="Add Model"
                    >
                      <PlusIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium text-slate-400">Available Voices</span>
                    <span className="text-xs text-slate-500">{(config.available_voices_labeled || []).length} voices</span>
                  </div>

                  {/* Compact Voice List - 2 columns on larger screens */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {(config.available_voices_labeled || []).map((v, idx) => (
                      <div key={idx} className="group flex items-center gap-2 bg-slate-800/40 border border-slate-700/50 rounded-lg p-2 hover:border-purple-500/30 transition-all">
                        <div className="p-1.5 bg-purple-500/10 rounded text-purple-400">
                          <MicIcon className="w-4 h-4" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <input
                            type="text"
                            value={v.label}
                            onChange={(e) => updateVoice(idx, 'label', e.target.value)}
                            className="w-full bg-transparent border-none p-0 text-sm font-medium text-slate-200 placeholder-slate-600 focus:ring-0"
                            placeholder="Voice Name"
                          />
                          <input
                            type="text"
                            value={v.id}
                            onChange={(e) => updateVoice(idx, 'id', e.target.value)}
                            className="w-full bg-transparent border-none p-0 text-[11px] font-mono text-slate-500 focus:text-purple-400 focus:ring-0 transition-colors"
                            placeholder="voice_id"
                          />
                        </div>
                        <button
                          onClick={() => removeVoice(idx)}
                          className="p-1 rounded text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-colors opacity-0 group-hover:opacity-100"
                          title="Remove Voice"
                        >
                          <TrashIcon className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}

                    {/* Add New Voice - Compact */}
                    <div className="flex items-center gap-2 border border-dashed border-slate-700/50 rounded-lg p-2 hover:border-purple-500/40 transition-all">
                      <div className="p-1.5 bg-slate-800/50 rounded text-slate-500">
                        <PlusIcon className="w-4 h-4" />
                      </div>
                      <input
                        type="text"
                        value={newVoice.label}
                        onChange={(e) => setNewVoice(prev => ({ ...prev, label: e.target.value }))}
                        placeholder="Name"
                        className="w-20 bg-transparent border-none p-0 text-sm text-slate-300 placeholder-slate-500 focus:ring-0"
                      />
                      <input
                        type="text"
                        value={newVoice.id}
                        onChange={(e) => setNewVoice(prev => ({ ...prev, id: e.target.value }))}
                        placeholder="voice_id"
                        className="flex-1 bg-transparent border-none p-0 text-xs font-mono text-slate-500 focus:text-purple-400 focus:ring-0"
                      />
                      <button
                        onClick={addVoice}
                        disabled={!newVoice.id.trim()}
                        className="p-1 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded transition-colors"
                        title="Add Voice"
                      >
                        <PlusIcon className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-6 mt-8">
                  {/* URLs Section */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider">API Endpoints</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-1 flex items-center gap-2 focus-within:border-sky-500/50 focus-within:ring-1 focus-within:ring-sky-500/20 transition-all">
                        <div className="p-2 text-slate-500">
                          <GlobeIcon className="w-5 h-5" />
                        </div>
                        <div className="flex-1">
                          <label className="block text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-0.5">Ollama URL</label>
                          <input
                            type="text"
                            value={config.ollama_base_url}
                            onChange={(e) => updateField('ollama_base_url', e.target.value)}
                            placeholder="http://localhost:11434"
                            className="w-full bg-transparent border-none p-0 text-sm text-slate-200 placeholder-slate-600 focus:ring-0"
                          />
                        </div>
                      </div>
                      <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-1 flex items-center gap-2 focus-within:border-sky-500/50 focus-within:ring-1 focus-within:ring-sky-500/20 transition-all">
                        <div className="p-2 text-slate-500">
                          <GlobeIcon className="w-5 h-5" />
                        </div>
                        <div className="flex-1">
                          <label className="block text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-0.5">OpenAI URL</label>
                          <input
                            type="text"
                            value={config.openai_base_url || ''}
                            onChange={(e) => updateField('openai_base_url', e.target.value)}
                            placeholder="http://localhost:12434/v1"
                            className="w-full bg-transparent border-none p-0 text-sm text-slate-200 placeholder-slate-600 focus:ring-0"
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* API Keys Section */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider">API Keys</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {[
                        { label: 'OpenAI Key', value: openaiApiKey, setter: setOpenaiApiKey, isSet: config.openai_api_key_set, placeholder: 'sk-...' },
                        { label: 'Google Key', value: googleApiKey, setter: setGoogleApiKey, isSet: config.google_api_key_set, placeholder: 'AIza...' },
                        { label: 'OpenRouter Key', value: openrouterApiKey, setter: setOpenrouterApiKey, isSet: config.openrouter_api_key_set, placeholder: 'sk-or-...' },
                        { label: 'AGNO Key', value: agnoApiKey, setter: setAgnoApiKey, isSet: config.agno_api_key_set, placeholder: 'Monitoring Key' },
                      ].map((item, i) => (
                        <div key={i} className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-1 flex items-center gap-2 focus-within:border-sky-500/50 focus-within:ring-1 focus-within:ring-sky-500/20 transition-all">
                          <div className="p-2 text-slate-500">
                            <KeyIcon className="w-5 h-5" />
                          </div>
                          <div className="flex-1">
                            <div className="flex justify-between items-center pr-2">
                              <label className="block text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-0.5">{item.label}</label>
                              {item.isSet && <span className="text-[10px] text-green-500 font-medium flex items-center gap-1"><CheckIcon className="w-3 h-3" /> Set</span>}
                            </div>
                            <input
                              type="password"
                              value={item.value}
                              onChange={(e) => item.setter(e.target.value)}
                              placeholder={item.isSet ? '••••••••••••••••' : item.placeholder}
                              className="w-full bg-transparent border-none p-0 text-sm text-slate-200 placeholder-slate-600 focus:ring-0 font-mono"
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Toggles */}
                  <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-4 flex items-center justify-between hover:bg-slate-800/50 transition-all cursor-pointer" onClick={() => updateField('gemini_search_enabled', !config.gemini_search_enabled)}>
                    <div className="flex items-center gap-4">
                      <div className={`p-2 rounded-lg ${config.gemini_search_enabled ? 'bg-sky-500/20 text-sky-400' : 'bg-slate-700/30 text-slate-500'}`}>
                        <SearchIcon className="w-5 h-5" />
                      </div>
                      <div>
                        <span className="block text-sm font-medium text-slate-200">Gemini Search</span>
                        <span className="block text-xs text-slate-400">Enable Google Search tool for Gemini models</span>
                      </div>
                    </div>
                    <div className={`w-11 h-6 rounded-full transition-colors relative ${config.gemini_search_enabled ? 'bg-sky-600' : 'bg-slate-700'}`}>
                      <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${config.gemini_search_enabled ? 'left-6' : 'left-1'}`} />
                    </div>
                  </div>
                </div>
              </section>

              {/* MCP Settings Card */}
              <section className="bg-slate-900/30 backdrop-blur-md border border-slate-500/30 rounded-xl p-6 space-y-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="p-2 bg-orange-500/10 rounded-lg text-orange-500">
                    <ServerIcon className="w-6 h-6" />
                  </div>
                  <h2 className="text-xl font-bold text-slate-200">MCP Settings</h2>
                </div>

                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
                  <div className="w-full">
                    <CustomDropdown
                      label="Transport Mode"
                      options={['streamable-http', 'stdio']}
                      value={config.mcp_transport}
                      onChange={(val) => updateField('mcp_transport', val)}
                    />
                  </div>
                </div>

                {config.mcp_transport === 'streamable-http' && (
                  <div className="space-y-6">
                    {/* Autonomous Mode Section - Docker Gateway Tools */}
                    <div className="space-y-3">
                      {/* Compact Header */}
                      <div className="relative overflow-hidden rounded-lg p-[1px] bg-slate-700/50">
                        <div className="relative bg-slate-900/95 backdrop-blur-sm rounded-lg p-3">
                          {/* Header */}
                          <div className="flex items-center justify-between mb-1.5 relative z-10">
                            <div className="flex items-center gap-2">
                              <div className="p-1.5 bg-orange-800/60 rounded">
                                <svg className="w-4 h-4 text-orange-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                </svg>
                              </div>
                              <h3 className="text-sm font-medium text-slate-300">
                                Autonomous Mode
                              </h3>
                            </div>
                            <span className="flex items-center gap-1 text-[10px] font-medium bg-slate-800 text-slate-400 px-2 py-1 rounded border border-slate-600/50">
                              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                              </svg>
                              Exclusive
                            </span>
                          </div>

                          <p className="text-[10px] text-slate-500 relative z-10">
                            Only one Autonomous Mode server can be selected at a time.
                          </p>
                        </div>
                      </div>

                      {/* Server Entries */}
                      <div className="grid grid-cols-1 gap-2">
                        {(config.mcp_servers || []).map((srv, idx) => {
                          // Use is_autonomous flag with fallback to URL pattern for backward compatibility
                          const isAutonomous = srv.is_autonomous ?? srv.url.toLowerCase().includes('mcp-gateway');
                          if (!isAutonomous) return null;
                          return (
                            <div key={idx} className="group relative overflow-hidden rounded-lg p-[1px] bg-slate-700/60 hover:bg-orange-800/40 transition-all duration-200">
                              <div className="relative bg-slate-900/95 backdrop-blur-sm rounded-lg p-3 flex items-center gap-3">
                                <div className="p-1.5 bg-orange-800/50 rounded relative z-10">
                                  <GlobeIcon className="w-4 h-4 text-orange-300" />
                                </div>
                                <div className="flex-1 min-w-0 relative z-10">
                                  <input type="text" value={srv.label} onChange={(e) => updateServer(idx, 'label', e.target.value)} className="w-full bg-transparent border-none p-0 text-sm font-medium text-slate-200 focus:ring-0 placeholder-slate-500" placeholder="Server Label" />
                                  <input type="text" value={srv.url} onChange={(e) => updateServer(idx, 'url', e.target.value)} className="w-full bg-transparent border-none p-0 text-[11px] text-slate-500 focus:text-slate-400 focus:ring-0 font-mono transition-colors" placeholder="http://host.docker.internal:8087/mcp" />
                                </div>
                                <button onClick={() => removeServer(idx)} className="p-1.5 rounded text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-all opacity-0 group-hover:opacity-100 relative z-10">
                                  <TrashIcon className="w-4 h-4" />
                                </button>
                              </div>
                            </div>
                          );
                        })}

                        {/* Add Autonomous Mode Server Button */}
                        {(config.mcp_servers || []).filter(srv => srv.is_autonomous ?? srv.url.toLowerCase().includes('mcp-gateway')).length === 0 && (
                          <button
                            onClick={() => {
                              setConfig(prev => prev ? {
                                ...prev,
                                mcp_servers: [...(prev.mcp_servers || []), { label: 'Docker Tools Container', url: 'http://mcp-gateway:8080/mcp', is_autonomous: true }]
                              } : prev);
                            }}
                            className="group relative rounded-lg border border-dashed border-slate-600/60 hover:border-slate-500 bg-slate-900/50 hover:bg-slate-800/50 transition-all duration-200"
                          >
                            <div className="p-3 flex items-center gap-3">
                              <div className="p-1.5 bg-slate-800 rounded text-slate-500 group-hover:text-orange-400 transition-colors">
                                <PlusIcon className="w-4 h-4" />
                              </div>
                              <div className="flex-1 text-left">
                                <span className="block text-sm font-medium text-slate-400 group-hover:text-slate-300 transition-colors">Add Autonomous Server</span>
                                <span className="block text-[10px] text-slate-600">Any URL - port and host configurable</span>
                              </div>
                            </div>
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="border-t border-slate-700/50"></div>

                    {/* Regular Web Tools Section */}
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-400">Web Tools</span>
                        <span className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded">HTTP</span>
                      </div>
                      <div className="grid grid-cols-1 gap-3">
                        {(config.mcp_servers || []).map((srv, idx) => {
                          // Use is_autonomous flag with fallback to URL pattern
                          const isAutonomous = srv.is_autonomous ?? srv.url.toLowerCase().includes('mcp-gateway');
                          if (isAutonomous) return null;
                          return (
                            <div key={idx} className="group relative bg-slate-800/40 border border-slate-700/50 rounded-xl p-3 flex items-center gap-3 hover:border-sky-500/30 transition-all">
                              <div className="p-2 bg-slate-800 rounded-lg text-slate-500">
                                <GlobeIcon className="w-5 h-5" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <input type="text" value={srv.label} onChange={(e) => updateServer(idx, 'label', e.target.value)} className="w-full bg-transparent border-none p-0 text-sm font-medium text-slate-200 focus:ring-0" placeholder="Server Label" />
                                <input type="text" value={srv.url} onChange={(e) => updateServer(idx, 'url', e.target.value)} className="w-full bg-transparent border-none p-0 text-xs text-slate-500 focus:text-sky-400 focus:ring-0 font-mono" placeholder="https://..." />
                              </div>
                              <button onClick={() => removeServer(idx)} className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-colors opacity-0 group-hover:opacity-100">
                                <TrashIcon className="w-4 h-4" />
                              </button>
                            </div>
                          );
                        })}

                        {/* Add Server */}
                        <div className="group relative border-2 border-dashed border-slate-700/50 rounded-xl p-3 flex items-center gap-3 hover:border-sky-500/40 hover:bg-slate-800/30 transition-all">
                          <div className="p-2 bg-slate-800 rounded-lg text-slate-500 group-hover:text-sky-400 transition-colors">
                            <PlusIcon className="w-5 h-5" />
                          </div>
                          <div className="flex-1 min-w-0 space-y-1">
                            <input type="text" value={newServer.label} onChange={(e) => setNewServer(prev => ({ ...prev, label: e.target.value }))} placeholder="New Server Label" className="w-full bg-transparent border-none p-0 text-sm font-medium text-slate-300 focus:ring-0" />
                            <input type="text" value={newServer.url} onChange={(e) => setNewServer(prev => ({ ...prev, url: e.target.value }))} placeholder="https://mcp-server.com/sse or http://mcp-gateway:8080/mcp" className="w-full bg-transparent border-none p-0 text-xs text-slate-500 focus:text-sky-400 focus:ring-0 font-mono" />
                          </div>
                          <button onClick={addServer} className="p-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white shadow-lg shadow-sky-900/20 transition-all">
                            <PlusIcon className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                      <p className="text-xs text-slate-500 italic">
                        Tip: Add a server with "mcp-gateway" in the URL to create an Autonomous Mode entry.
                      </p>
                    </div>
                  </div>
                )}

                {config.mcp_transport === 'stdio' && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-slate-400">Stdio Tools</span>
                      <span className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded">Local</span>
                    </div>
                    <div className="grid grid-cols-1 gap-3">
                      {(config.mcp_stdio_tools || []).map((tool, idx) => (
                        <div key={idx} className="group relative bg-slate-800/40 border border-slate-700/50 rounded-xl p-3 flex items-center gap-3 hover:border-green-500/30 transition-all">
                          <div className="p-2 bg-slate-800 rounded-lg text-slate-500">
                            <TerminalIcon className="w-5 h-5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <input type="text" value={tool.label} onChange={(e) => updateStdioTool(idx, 'label', e.target.value)} className="w-full bg-transparent border-none p-0 text-sm font-medium text-slate-200 focus:ring-0" placeholder="Tool Label" />
                            <input type="text" value={tool.command} onChange={(e) => updateStdioTool(idx, 'command', e.target.value)} className="w-full bg-transparent border-none p-0 text-xs text-slate-500 focus:text-green-400 focus:ring-0 font-mono" placeholder="npx -y ..." />
                          </div>
                          <button onClick={() => removeStdioTool(idx)} className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-colors opacity-0 group-hover:opacity-100">
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        </div>
                      ))}

                      {/* Add Tool */}
                      <div className="group relative border-2 border-dashed border-slate-700/50 rounded-xl p-3 flex items-center gap-3 hover:border-green-500/40 hover:bg-slate-800/30 transition-all">
                        <div className="p-2 bg-slate-800 rounded-lg text-slate-500 group-hover:text-green-400 transition-colors">
                          <PlusIcon className="w-5 h-5" />
                        </div>
                        <div className="flex-1 min-w-0 space-y-1">
                          <input type="text" value={newStdioTool.label} onChange={(e) => setNewStdioTool(prev => ({ ...prev, label: e.target.value }))} placeholder="New Tool Label" className="w-full bg-transparent border-none p-0 text-sm font-medium text-slate-300 focus:ring-0" />
                          <input type="text" value={newStdioTool.command} onChange={(e) => setNewStdioTool(prev => ({ ...prev, command: e.target.value }))} placeholder="npx -y @modelcontextprotocol/server-..." className="w-full bg-transparent border-none p-0 text-xs text-slate-500 focus:text-green-400 focus:ring-0 font-mono" />
                        </div>
                        <button onClick={addStdioTool} className="p-1.5 rounded-lg bg-green-600 hover:bg-green-500 text-white shadow-lg shadow-green-900/20 transition-all">
                          <PlusIcon className="w-4 h-4" />
                        </button>
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
      </div >
    </div >
  );
};
