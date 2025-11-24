"""
Carefully add multimodal checkboxes to ConfigPage.tsx
This script makes surgical modifications to avoid corruption.
"""

# Read the file
with open(r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the exact location - after the button with TrashIcon for model removal
# We need to insert right after the closing </div> of the flex row (line 309 area)

# Strategy: Find the model row structure and insert checkboxes before the closing of the mapped element
# Look for the pattern: </button>\n       </div>\n     ))}

old_pattern = '''                        <button onClick={() => removeModel(idx)} className={buttonRemoveIconStyle} title="Remove Model">
                          <TrashIcon className="w-5 h-5" />
                        </button>
                      </div>
                    ))}'''

new_pattern = '''                        <button onClick={() => removeModel(idx)} className={buttonRemoveIconStyle} title="Remove Model">
                          <TrashIcon className="w-5 h-5" />
                        </button>
                      </div>
                      {/* Multimodal Capabilities */}
                      <div className="flex items-center gap-4 mt-2 ml-4 text-xs">
                        <label className="flex items-center gap-2 text-slate-400 cursor-pointer hover:text-slate-300">
                          <input
                            type="checkbox"
                            checked={m.supports_images || false}
                            onChange={(e) => {
                              if (!config) return;
                              const newList = (config.available_models_labeled || []).map((model, i) => 
                                i === idx ? { ...model, supports_images: e.target.checked } : model
                              );
                              updateModelsList(newList);
                            }}
                            className="w-4 h-4 rounded border-slate-600 text-sky-600 focus:ring-sky-500 bg-slate-700"
                          />
                          <span>📷 Images</span>
                        </label>
                        <label className="flex items-center gap-2 text-slate-400 cursor-pointer hover:text-slate-300">
                          <input
                            type="checkbox"
                            checked={m.supports_audio || false}
                            onChange={(e) => {
                              if (!config) return;
                              const newList = (config.available_models_labeled || []).map((model, i) => 
                                i === idx ? { ...model, supports_audio: e.target.checked } : model
                              );
                              updateModelsList(newList);
                            }}
                            className="w-4 h-4 rounded border-slate-600 text-sky-600 focus:ring-sky-500 bg-slate-700"
                          />
                          <span>🎵 Audio</span>
                        </label>
                        <label className="flex items-center gap-2 text-slate-400 cursor-pointer hover:text-slate-300">
                          <input
                            type="checkbox"
                            checked={m.supports_videos || false}
                            onChange={(e) => {
                              if (!config) return;
                              const newList = (config.available_models_labeled || []).map((model, i) => 
                                i === idx ? { ...model, supports_videos: e.target.checked } : model
                              );
                              updateModelsList(newList);
                            }}
                            className="w-4 h-4 rounded border-slate-600 text:ring-sky-500 bg-slate-700"
                          />
                          <span>🎬 Videos</span>
                        </label>
                      </div>
                    ))}'''

# Check if pattern exists
if old_pattern in content:
    # Make the replacement
    new_content = content.replace(old_pattern, new_pattern, 1)
    
    # Verify we only made one replacement and it's reasonable
    if new_content.count('supports_images') == 1 and new_content.count('supports_audio') == 1:
        # Write back
        with open(r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx', 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('✅ ConfigPage.tsx updated successfully with multimodal checkboxes!')
        print('   - Added 3 checkboxes: Images, Audio, Videos')
        print('   - Checkboxes appear below each model row')
    else:
        print('❌ ERROR: Replacement created unexpected structure')
        print(f'   supports_images count: {new_content.count("supports_images")}')
        print(f'   supports_audio count: {new_content.count("supports_audio")}')
else:
    print('❌ ERROR: Could not find the expected pattern in ConfigPage.tsx')
    print('   The file structure may have changed.')
    print('   Looking for: </button> followed by </div> followed by )))')
