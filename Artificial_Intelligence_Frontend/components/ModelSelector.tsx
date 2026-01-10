import React, { useState, useRef, useEffect } from 'react';
import { CubeIcon, CheckIcon } from './icons';

interface ModelSelectorProps {
    currentModel: string;
    onModelChange: (modelId: string) => void;
    availableModels: { label: string; id: string; provider?: string }[];
}

const ChevronDownIcon = ({ className }: { className?: string }) => (
    <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
    >
        <polyline points="6 9 12 15 18 9" />
    </svg>
);

/**
 * Collapsible model selector component with provider tabs.
 * Shows current model in collapsed state, expands to show provider tabs and model list.
 */
export const ModelSelector: React.FC<ModelSelectorProps> = ({
    currentModel,
    onModelChange,
    availableModels,
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const [selectedProvider, setSelectedProvider] = useState<string>('');
    const containerRef = useRef<HTMLDivElement>(null);

    // Group models by provider
    const modelsByProvider = availableModels.reduce((acc, m) => {
        let provider = m.provider;
        if (!provider) {
            if (m.id.startsWith('openrouter/')) {
                provider = 'openrouter';
            } else if (m.id.startsWith('gemini/')) {
                provider = 'gemini';
            } else if (m.id.startsWith('gpt/') || m.id.startsWith('openai/')) {
                provider = 'openai';
            } else {
                provider = 'ollama';
            }
        }
        if (!acc[provider]) acc[provider] = [];
        acc[provider].push(m);
        return acc;
    }, {} as Record<string, Array<{ label: string; id: string; provider?: string }>>);

    const providers = Object.keys(modelsByProvider);

    // Get current model info
    const currentModelInfo = availableModels.find(m => m.id === currentModel);
    const currentModelLabel = currentModelInfo?.label || currentModel;

    // Set initial provider based on current model
    useEffect(() => {
        if (providers.length > 0 && !selectedProvider) {
            let initialProvider = providers[0];
            for (const [prov, models] of Object.entries(modelsByProvider)) {
                if (models.some(m => m.id === currentModel)) {
                    initialProvider = prov;
                    break;
                }
            }
            setSelectedProvider(initialProvider);
        }
    }, [availableModels, currentModel]);

    // Close on outside click
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isOpen]);

    // Close on Escape key
    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape' && isOpen) {
                setIsOpen(false);
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [isOpen]);

    const handleModelSelect = (modelId: string) => {
        onModelChange(modelId);
        setIsOpen(false);
    };

    if (!availableModels || availableModels.length === 0) {
        return (
            <div className="text-xs text-slate-500">No models configured.</div>
        );
    }

    return (
        <div ref={containerRef} className="relative">
            {/* Header / Trigger Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={`
                    w-full flex items-center justify-between
                    bg-slate-800/50 backdrop-blur-sm
                    border border-slate-600/50
                    text-slate-200 text-xs
                    rounded-lg px-3 py-2
                    hover:bg-slate-700/50 hover:border-slate-500
                    focus:outline-none focus:ring-2 focus:ring-sky-500/50
                    transition-all duration-200 ease-in-out
                    ${isOpen ? 'ring-2 ring-sky-500/50 border-sky-500' : ''}
                `}
            >
                <div className="flex items-center gap-1.5 min-w-0">
                    <CubeIcon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span className="font-medium shrink-0">Model:</span>
                    <span className="text-sky-400 font-semibold truncate" title={currentModelLabel}>
                        {currentModelLabel}
                    </span>
                </div>
                <ChevronDownIcon
                    className={`w-4 h-4 text-slate-400 shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                />
            </button>

            {/* Dropdown Panel */}
            <div
                className={`
                    absolute z-50 w-full mt-2
                    bg-slate-900/95 backdrop-blur-xl
                    border border-slate-700/50
                    rounded-lg shadow-xl shadow-black/50
                    overflow-hidden
                    transition-all duration-200 ease-out origin-top
                    ${isOpen
                        ? 'opacity-100 scale-100 translate-y-0'
                        : 'opacity-0 scale-95 -translate-y-2 pointer-events-none'}
                `}
            >
                {/* Provider Tabs */}
                {providers.length > 1 && (
                    <div className="flex border-b border-slate-700/50 overflow-x-auto scrollbar-thin scrollbar-thumb-slate-700">
                        {providers.map(provider => (
                            <button
                                key={provider}
                                onClick={() => setSelectedProvider(provider)}
                                className={`
                                    flex-1 min-w-0 px-2 py-2 text-xs font-medium capitalize
                                    transition-colors duration-150 truncate
                                    ${selectedProvider === provider
                                        ? 'text-sky-400 border-b-2 border-sky-500 bg-sky-500/10'
                                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}
                                `}
                                title={provider}
                            >
                                {provider}
                            </button>
                        ))}
                    </div>
                )}

                {/* Model List */}
                <div className="max-h-48 overflow-y-auto p-2 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                    <div className="space-y-1">
                        {(modelsByProvider[selectedProvider] || []).map((model) => {
                            const isSelected = currentModel === model.id;
                            return (
                                <button
                                    key={model.id}
                                    onClick={() => handleModelSelect(model.id)}
                                    className={`
                                        w-full text-left px-3 py-2 text-sm rounded-md
                                        transition-all duration-150
                                        flex items-center justify-between
                                        ${isSelected
                                            ? 'bg-sky-600/20 text-sky-400'
                                            : 'text-slate-300 hover:bg-slate-800'}
                                    `}
                                    title={model.label}
                                >
                                    <span className="font-medium truncate">{model.label}</span>
                                    {isSelected && <CheckIcon className="w-4 h-4 text-sky-400 shrink-0 ml-2" />}
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Footer hint */}
                <div className="px-3 py-2 bg-slate-800/30 border-t border-slate-700/50">
                    <p className="text-[10px] text-slate-500">
                        Choose the AI model to power your assistant.
                    </p>
                </div>
            </div>
        </div>
    );
};
