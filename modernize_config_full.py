"""
Modernize the rest of ConfigPage.tsx (Voices, API Keys, MCP Settings).
"""

import re

path = r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Imports
# -----------------
old_import = "import { PlusIcon, TrashIcon, ImageIcon, VideoIcon } from './icons';"
new_import = "import { PlusIcon, TrashIcon, ImageIcon, VideoIcon, MicIcon, KeyIcon, GlobeIcon, ServerIcon, TerminalIcon, SearchIcon } from './icons';"
content = content.replace(old_import, new_import)

# 2. Modernize Voices Section
# ---------------------------
# Target: <div>...Available Voices...</div> (the whole block)
# We'll look for the start of "Available Voices" and the end of that block.
# The block structure is:
# <div>
#   <span ...>Available Voices</span>
#   <div space-y-2>
#     ... map ...
#     ... add new ...
#   </div>
# </div>

voices_start_marker = '<span className="block text-sm font-medium text-slate-400 mb-2">Available Voices</span>'
# We need to replace the surrounding div too if possible, or just the content.
# Let's replace the content starting from the span.

voices_new_content = '''<span className="block text-sm font-medium text-slate-400 mb-3">Available Voices</span>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {(config.available_voices_labeled || []).map((v, idx) => (
                      <div key={idx} className="group relative bg-slate-800/40 border border-slate-700/50 rounded-xl p-3 flex items-center gap-3 transition-all hover:border-purple-500/30 hover:shadow-lg hover:shadow-purple-500/5">
                        <div className="p-2 bg-purple-500/10 rounded-lg text-purple-400">
                          <MicIcon className="w-5 h-5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <input 
                            type="text" 
                            value={v.label} 
                            onChange={(e) => updateVoice(idx, 'label', e.target.value)} 
                            className="w-full bg-transparent border-none p-0 text-sm font-medium text-slate-200 placeholder-slate-600 focus:ring-0" 
                            placeholder="Voice Label" 
                          />
                          <input 
                            type="text" 
                            value={v.id} 
                            onChange={(e) => updateVoice(idx, 'id', e.target.value)} 
                            className="w-full bg-transparent border-none p-0 text-xs font-mono text-slate-500 focus:text-purple-400 focus:ring-0 transition-colors" 
                            placeholder="voice_id" 
                          />
                        </div>
                        <button 
                          onClick={() => removeVoice(idx)} 
                          className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-colors opacity-0 group-hover:opacity-100" 
                          title="Remove Voice"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                    
                    {/* Add Voice Card */}
                    <div className="group relative border-2 border-dashed border-slate-700/50 rounded-xl p-3 flex items-center gap-3 hover:border-purple-500/40 hover:bg-slate-800/30 transition-all">
                      <div className="p-2 bg-slate-800 rounded-lg text-slate-500 group-hover:text-purple-400 transition-colors">
                        <PlusIcon className="w-5 h-5" />
                      </div>
                      <div className="flex-1 min-w-0 space-y-1">
                        <input 
                          type="text" 
                          value={newVoice.label} 
                          onChange={(e) => setNewVoice(prev => ({ ...prev, label: e.target.value }))} 
                          placeholder="New Voice Label" 
                          className="w-full bg-transparent border-none p-0 text-sm font-medium text-slate-300 placeholder-slate-500 focus:ring-0" 
                        />
                        <input 
                          type="text" 
                          value={newVoice.id} 
                          onChange={(e) => setNewVoice(prev => ({ ...prev, id: e.target.value }))} 
                          placeholder="voice_id" 
                          className="w-full bg-transparent border-none p-0 text-xs font-mono text-slate-500 focus:text-purple-400 focus:ring-0 transition-colors" 
                        />
                      </div>
                      <button 
                        onClick={addVoice} 
                        className="p-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-900/20 transition-all"
                        title="Add Voice"
                      >
                        <PlusIcon className="w-4 h-4" />
                      </button>
                    </div>
                  </div>'''

# Find start of voices section
v_start = content.find(voices_start_marker)
# Find end of voices section. It ends before the first API Key label.
# The next section starts with <label className="block">...AI Base URL
api_start_marker = '<span className="block text-sm font-medium text-slate-400 mb-2">AI Base URL (Ollama)</span>'
v_end = content.find(api_start_marker)
# We need to back up from v_end to find the closing divs of the voices section.
# The structure before api_start_marker is:
# </div> (closes space-y-2)
# </div> (closes outer div)
# <label ...> (starts API key)

# Let's replace from v_start to the character before the <label> tag that contains api_start_marker.
# We need to find the <label> tag.
label_start = content.rfind('<label', 0, v_end)
# So we replace from v_start to label_start.
# But wait, the voices section is wrapped in a <div>.
# My new content replaces the inner content.
# So I should keep the outer div?
# The original code:
# <div>
#   <span>Available Voices</span>
#   ...
# </div>
# <label>...

# My replacement starts with <span>.
# So I should replace from v_start to the closing </div> of the inner div?
# No, let's replace the whole block if possible.
# But finding the exact closing div is hard.
# Let's replace the inner content.
# The inner content is <span>...</span> <div space-y-2>...</div>
# The outer div remains.
# So I need to find where the inner div ends.
# It ends just before the outer div closes.
# The outer div closes just before <label>.
# So the sequence is </div> </div> <label>.
# I want to replace up to the second to last </div> before label_start.

# Let's try a different strategy: Regex replacement for the specific block structure.
# But regex on large multiline HTML is fragile.

# Let's stick to markers.
# I will replace from voices_start_marker up to label_start.
# And I will ensure my new content closes the divs properly.
# Original:
# <div> [start_marker] ... </div> </div> [label_start]
# My new content:
# [start_marker] ... </div>
# So I need to add one </div> at the end to close the outer div.
# So replacement = voices_new_content + "\n</div>\n"

content = content[:v_start] + voices_new_content + "\n                </div>\n                " + content[label_start:]


# 3. Modernize API Keys & URLs
# ----------------------------
# We will replace the block of <label>...</label> elements.
# From AI Base URL to Enable Gemini Search.

# Start: <label className="block"> (the one containing AI Base URL)
# End: </section> (end of the first section)

# Actually, let's replace the whole block of inputs.
# I'll construct the new API section.

api_section_new = '''<div className="grid grid-cols-1 gap-6 mt-8">
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
                </div>'''

# We need to replace from the start of the first label (AI Base URL) to the end of the section (Enable Gemini Search).
# The section ends with </section>.
# So we replace from label_start (which we found earlier) to the last </label> closing tag + closing div?
# Let's look at the structure again.
# <label>...AI Base URL...</label>
# ...
# <label>...Gemini Search...</label>
# </section>

# So we replace from label_start to the index of </section>.
section_end = content.find('</section>', label_start)
content = content[:label_start] + api_section_new + "\n              " + content[section_end:]


# 4. Modernize MCP Settings
# -------------------------
# Target: <section ...> <h2 ...>MCP Settings</h2> ... </section>
# We'll replace the inner content of the section.

mcp_header = '<h2 className="text-xl font-bold">MCP Settings</h2>'
mcp_start = content.find(mcp_header)
mcp_section_end = content.find('</section>', mcp_start)

# We want to keep the header, or replace it with a better one.
# Let's replace the whole inner content after the header.
# Or replace the whole section block.

mcp_new_content = '''<section className="bg-slate-900/30 backdrop-blur-md border border-slate-500/30 rounded-xl p-6 space-y-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="p-2 bg-orange-500/10 rounded-lg text-orange-500">
                    <ServerIcon className="w-6 h-6" />
                  </div>
                  <h2 className="text-xl font-bold text-slate-200">MCP Settings</h2>
                </div>

                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
                  <label className="block">
                    <span className="block text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Transport Mode</span>
                    <select 
                      value={config.mcp_transport} 
                      onChange={(e) => updateField('mcp_transport', e.target.value)} 
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:border-orange-500 focus:ring-1 focus:ring-orange-500 outline-none transition-all"
                    >
                      <option value="streamable-http">Streamable HTTP (Remote)</option>
                      <option value="stdio">Stdio (Local Process)</option>
                    </select>
                  </label>
                </div>

                {config.mcp_transport === 'streamable-http' && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-slate-400">MCP Servers</span>
                      <span className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded">HTTP</span>
                    </div>
                    <div className="grid grid-cols-1 gap-3">
                      {(config.mcp_servers || []).map((srv, idx) => (
                        <div key={idx} className="group relative bg-slate-800/40 border border-slate-700/50 rounded-xl p-3 flex items-center gap-3 hover:border-orange-500/30 transition-all">
                          <div className="p-2 bg-slate-800 rounded-lg text-slate-500">
                            <GlobeIcon className="w-5 h-5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <input type="text" value={srv.label} onChange={(e) => updateServer(idx, 'label', e.target.value)} className="w-full bg-transparent border-none p-0 text-sm font-medium text-slate-200 focus:ring-0" placeholder="Server Label" />
                            <input type="text" value={srv.url} onChange={(e) => updateServer(idx, 'url', e.target.value)} className="w-full bg-transparent border-none p-0 text-xs text-slate-500 focus:text-orange-400 focus:ring-0 font-mono" placeholder="https://..." />
                          </div>
                          <button onClick={() => removeServer(idx)} className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-colors opacity-0 group-hover:opacity-100">
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                      
                      {/* Add Server */}
                      <div className="group relative border-2 border-dashed border-slate-700/50 rounded-xl p-3 flex items-center gap-3 hover:border-orange-500/40 hover:bg-slate-800/30 transition-all">
                        <div className="p-2 bg-slate-800 rounded-lg text-slate-500 group-hover:text-orange-400 transition-colors">
                          <PlusIcon className="w-5 h-5" />
                        </div>
                        <div className="flex-1 min-w-0 space-y-1">
                          <input type="text" value={newServer.label} onChange={(e) => setNewServer(prev => ({ ...prev, label: e.target.value }))} placeholder="New Server Label" className="w-full bg-transparent border-none p-0 text-sm font-medium text-slate-300 focus:ring-0" />
                          <input type="text" value={newServer.url} onChange={(e) => setNewServer(prev => ({ ...prev, url: e.target.value }))} placeholder="https://mcp-server.com/sse" className="w-full bg-transparent border-none p-0 text-xs text-slate-500 focus:text-orange-400 focus:ring-0 font-mono" />
                        </div>
                        <button onClick={addServer} className="p-1.5 rounded-lg bg-orange-600 hover:bg-orange-500 text-white shadow-lg shadow-orange-900/20 transition-all">
                          <PlusIcon className="w-4 h-4" />
                        </button>
                      </div>
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
              </section>'''

# Replace the whole MCP section
# Find the start of the section tag
section_start = content.rfind('<section', 0, mcp_start)
content = content[:section_start] + mcp_new_content + content[mcp_section_end+10:]

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ ConfigPage.tsx fully modernized!')
