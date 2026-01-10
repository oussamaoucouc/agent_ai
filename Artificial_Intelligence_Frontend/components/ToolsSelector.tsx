import React, { useState, useRef, useEffect } from 'react';
import { McpToolItem } from '../types';
import { ToolIcon, CheckIcon, CloseIcon } from './icons';
import { SelectionChip } from './SelectionChip';

interface ToolsSelectorProps {
    // MCP SSE tools (Web Tools and Docker Gateway)
    mcpToolsCatalog: McpToolItem[];
    selectedMcpTools: string[];
    onSelectedMcpToolsChange: (labels: string[]) => void;
    // MCP Stdio tools (Local Tools)
    mcpStdioCatalog: { label: string; command: string }[];
    selectedMcpStdio: string[];
    onSelectedMcpStdioChange: (cmds: string[]) => void;
    // State flags
    canSelectTools: boolean;
    isSettingsSyncing?: boolean;
    onShowConfirmation?: (title: string, message: string, onConfirm: () => void) => void;
}

type ToolCategory = 'docker' | 'web' | 'local';

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

const DockerIcon = ({ className }: { className?: string }) => (
    <svg className={className} fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M13.983 11.078h2.119a.186.186 0 00.186-.185V9.006a.186.186 0 00-.186-.186h-2.119a.185.185 0 00-.185.186v1.887c0 .102.083.185.185.185zm-2.954-5.43h2.118a.186.186 0 00.186-.186V3.574a.186.186 0 00-.186-.185h-2.118a.185.185 0 00-.185.185v1.888c0 .102.082.185.185.186zm0 2.716h2.118a.187.187 0 00.186-.186V6.29a.186.186 0 00-.186-.185h-2.118a.185.185 0 00-.185.185v1.887c0 .102.082.186.185.186zm-2.93 0h2.12a.186.186 0 00.184-.186V6.29a.185.185 0 00-.185-.185H8.1a.185.185 0 00-.185.185v1.887c0 .102.083.186.185.186zm-2.964 0h2.119a.186.186 0 00.185-.186V6.29a.185.185 0 00-.185-.185H5.136a.186.186 0 00-.186.185v1.887c0 .102.084.186.186.186zm5.893 2.715h2.118a.186.186 0 00.186-.185V9.006a.186.186 0 00-.186-.186h-2.118a.185.185 0 00-.185.186v1.887c0 .102.082.185.185.185zm-2.93 0h2.12a.185.185 0 00.184-.185V9.006a.185.185 0 00-.184-.186h-2.12a.185.185 0 00-.184.186v1.887c0 .102.083.185.185.185zm-2.964 0h2.119a.185.185 0 00.185-.185V9.006a.185.185 0 00-.185-.186h-2.12a.186.186 0 00-.185.186v1.887c0 .102.084.185.186.185zm-2.92 0h2.12a.185.185 0 00.184-.185V9.006a.185.185 0 00-.184-.186h-2.12a.185.185 0 00-.184.186v1.887c0 .102.082.185.185.185zM23.763 9.89c-.065-.051-.672-.51-1.954-.51-.338.001-.676.03-1.01.087-.248-1.7-1.653-2.53-1.716-2.566l-.344-.199-.226.327c-.284.438-.49.922-.612 1.43-.23.97-.09 1.882.403 2.661-.595.332-1.55.413-1.744.42H.751a.751.751 0 00-.75.748 11.376 11.376 0 00.692 4.062c.545 1.428 1.355 2.48 2.41 3.124 1.18.723 3.1 1.137 5.275 1.137.983.003 1.963-.086 2.93-.266a12.248 12.248 0 003.823-1.389c.98-.567 1.86-1.288 2.61-2.136 1.252-1.418 1.998-2.997 2.553-4.4h.221c1.372 0 2.215-.549 2.68-1.009.309-.293.55-.65.707-1.046l.098-.288z" />
    </svg>
);

const GlobeIcon = ({ className }: { className?: string }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
    </svg>
);

const TerminalIcon = ({ className }: { className?: string }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
);

/**
 * Collapsible tools selector with categorized tabs (Docker/Web/Local).
 * Shows selection chips in collapsed state for quick visibility.
 */
export const ToolsSelector: React.FC<ToolsSelectorProps> = ({
    mcpToolsCatalog,
    selectedMcpTools,
    onSelectedMcpToolsChange,
    mcpStdioCatalog,
    selectedMcpStdio,
    onSelectedMcpStdioChange,
    canSelectTools,
    isSettingsSyncing = false,
    onShowConfirmation,
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const [activeTab, setActiveTab] = useState<ToolCategory>('web');
    const containerRef = useRef<HTMLDivElement>(null);

    // Docker MCP Gateway detection
    const isDockerGateway = (tool: McpToolItem): boolean => {
        if (tool.is_autonomous !== undefined) {
            return tool.is_autonomous;
        }
        return tool.url.toLowerCase().includes('mcp-gateway');
    };

    // Categorize tools
    const dockerTools = mcpToolsCatalog.filter(isDockerGateway);
    const webTools = mcpToolsCatalog.filter(tool => !isDockerGateway(tool));
    const localTools = mcpStdioCatalog;

    // Check if Docker gateway is active
    const isDockerGatewayActive = dockerTools.some(
        tool => selectedMcpTools.includes(tool.label)
    );

    // Calculate total selections
    const totalSelected = selectedMcpTools.length + selectedMcpStdio.length;

    // Set initial tab based on available tools
    useEffect(() => {
        if (dockerTools.length > 0 && isDockerGatewayActive) {
            setActiveTab('docker');
        } else if (webTools.length > 0) {
            setActiveTab('web');
        } else if (localTools.length > 0) {
            setActiveTab('local');
        }
    }, []);

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

    const toggleMcpTool = (label: string) => {
        if (!canSelectTools) return;

        const tool = mcpToolsCatalog.find(t => t.label === label);
        const isSelectingGateway = tool && isDockerGateway(tool);
        const isAlreadySelected = selectedMcpTools.includes(label);

        // Case 1: Deselecting Docker gateway
        if (isSelectingGateway && isAlreadySelected) {
            onSelectedMcpToolsChange([]);
            return;
        }

        // Case 2: Selecting Docker gateway - show confirmation
        if (isSelectingGateway && !isAlreadySelected) {
            if (onShowConfirmation) {
                onShowConfirmation(
                    'Docker Tools Mode',
                    'Selecting Docker Tools enables exclusive mode. All other Web Tools and Local Tools will be cleared. Do you want to continue?',
                    () => {
                        onSelectedMcpToolsChange([label]);
                        onSelectedMcpStdioChange([]);
                    }
                );
            } else {
                onSelectedMcpToolsChange([label]);
                onSelectedMcpStdioChange([]);
            }
            return;
        }

        // Case 3: Docker gateway is active and user tries to select another tool
        if (isDockerGatewayActive && !isSelectingGateway) {
            return;
        }

        // Case 4: Normal toggle
        const nextLabels = isAlreadySelected
            ? selectedMcpTools.filter(l => l !== label)
            : [...selectedMcpTools, label];
        onSelectedMcpToolsChange(nextLabels);
    };

    const toggleMcpStdio = (cmd: string) => {
        if (!canSelectTools || isDockerGatewayActive) return;

        const next = selectedMcpStdio.includes(cmd)
            ? selectedMcpStdio.filter(c => c !== cmd)
            : [...selectedMcpStdio, cmd];
        onSelectedMcpStdioChange(next);
    };

    const removeWebTool = (label: string) => {
        if (!canSelectTools) return;
        onSelectedMcpToolsChange(selectedMcpTools.filter(l => l !== label));
    };

    const removeLocalTool = (cmd: string) => {
        if (!canSelectTools) return;
        onSelectedMcpStdioChange(selectedMcpStdio.filter(c => c !== cmd));
    };

    // Get selected items for chips (combine web and local selections, max 3 chips + overflow)
    const getSelectedItems = () => {
        const items: { label: string; onRemove: () => void }[] = [];

        // Add selected web tools (excluding docker gateway)
        webTools.forEach(tool => {
            if (selectedMcpTools.includes(tool.label)) {
                items.push({ label: tool.label, onRemove: () => removeWebTool(tool.label) });
            }
        });

        // Add selected local tools
        localTools.forEach(tool => {
            if (selectedMcpStdio.includes(tool.command)) {
                items.push({ label: tool.label, onRemove: () => removeLocalTool(tool.command) });
            }
        });

        return items;
    };

    const selectedItems = getSelectedItems();
    const visibleChips = selectedItems.slice(0, 3);
    const overflowCount = selectedItems.length - 3;

    const isDisabled = !canSelectTools || isSettingsSyncing;

    const getTabIcon = (tab: ToolCategory) => {
        switch (tab) {
            case 'docker': return <DockerIcon className="w-3.5 h-3.5" />;
            case 'web': return <GlobeIcon className="w-3.5 h-3.5" />;
            case 'local': return <TerminalIcon className="w-3.5 h-3.5" />;
        }
    };

    const getTabCount = (tab: ToolCategory) => {
        switch (tab) {
            case 'docker': return dockerTools.length;
            case 'web': return webTools.length;
            case 'local': return localTools.length;
        }
    };

    // Only show tabs that have tools
    const availableTabs: ToolCategory[] = [];
    if (dockerTools.length > 0) availableTabs.push('docker');
    if (webTools.length > 0) availableTabs.push('web');
    if (localTools.length > 0) availableTabs.push('local');

    if (availableTabs.length === 0) {
        return (
            <div className="text-xs text-slate-500">No tools configured.</div>
        );
    }

    return (
        <div ref={containerRef} className={`relative transition-opacity duration-200 ${isDisabled ? 'opacity-60' : ''}`}>
            {/* Header / Trigger Button */}
            <button
                onClick={() => !isDisabled && setIsOpen(!isOpen)}
                disabled={isDisabled}
                className={`
                    w-full flex flex-col gap-1.5
                    bg-slate-800/50 backdrop-blur-sm
                    border border-slate-600/50
                    text-slate-200 text-xs
                    rounded-lg px-3 py-2
                    ${!isDisabled ? 'hover:bg-slate-700/50 hover:border-slate-500 cursor-pointer' : 'cursor-not-allowed'}
                    focus:outline-none focus:ring-2 focus:ring-sky-500/50
                    transition-all duration-200 ease-in-out
                    ${isOpen && !isDisabled ? 'ring-2 ring-sky-500/50 border-sky-500' : ''}
                `}
            >
                {/* Top row: Icon, label, count, chevron */}
                <div className="flex items-center justify-between w-full">
                    <div className="flex items-center gap-1.5">
                        <ToolIcon className="w-3.5 h-3.5 text-slate-400" />
                        <span className="font-medium">Tools</span>
                        {totalSelected > 0 && (
                            <SelectionChip label={`${totalSelected} selected`} variant="count" />
                        )}
                        {isDockerGatewayActive && (
                            <span className="flex items-center gap-1 text-[9px] font-medium bg-sky-800/60 text-sky-200 px-1.5 py-0.5 rounded-full">
                                <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse"></span>
                                DOCKER
                            </span>
                        )}
                    </div>
                    <ChevronDownIcon
                        className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                    />
                </div>

                {/* Selection chips row - only when not in docker mode */}
                {!isDockerGatewayActive && visibleChips.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                        {visibleChips.map(item => (
                            <SelectionChip
                                key={item.label}
                                label={item.label}
                                onRemove={item.onRemove}
                                disabled={isDisabled}
                            />
                        ))}
                        {overflowCount > 0 && (
                            <SelectionChip label={`+${overflowCount} more`} variant="count" />
                        )}
                    </div>
                )}
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
                    ${isOpen && !isDisabled
                        ? 'opacity-100 scale-100 translate-y-0'
                        : 'opacity-0 scale-95 -translate-y-2 pointer-events-none'}
                `}
            >
                {/* Category Tabs */}
                <div className="flex border-b border-slate-700/50">
                    {availableTabs.map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`
                                flex-1 flex items-center justify-center gap-1.5 px-2 py-2 text-xs font-medium
                                transition-colors duration-150
                                ${activeTab === tab
                                    ? 'text-sky-400 border-b-2 border-sky-500 bg-sky-500/10'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}
                            `}
                        >
                            {getTabIcon(tab)}
                            <span className="capitalize">{tab}</span>
                            <span className="text-[10px] text-slate-500">({getTabCount(tab)})</span>
                        </button>
                    ))}
                </div>

                {/* Tab Content */}
                <div className="max-h-48 overflow-y-auto p-2 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                    {/* Docker Tools Tab */}
                    {activeTab === 'docker' && (
                        <div className="space-y-1">
                            {dockerTools.map(tool => {
                                const isSelected = selectedMcpTools.includes(tool.label);
                                return (
                                    <button
                                        key={tool.label}
                                        onClick={() => toggleMcpTool(tool.label)}
                                        disabled={!canSelectTools}
                                        className={`
                                            w-full text-left px-3 py-2 text-sm rounded-md
                                            transition-all duration-150
                                            flex items-center justify-between
                                            ${isSelected
                                                ? 'bg-sky-600/30 text-sky-300 border border-sky-500/50'
                                                : canSelectTools
                                                    ? 'text-slate-300 hover:bg-slate-800 border border-transparent'
                                                    : 'text-slate-500 cursor-not-allowed border border-transparent'}
                                        `}
                                    >
                                        <span className="flex items-center gap-2">
                                            <span className="text-base">⚡</span>
                                            <span className="font-medium">{tool.label}</span>
                                        </span>
                                        {isSelected && <CheckIcon className="w-4 h-4 text-sky-400" />}
                                    </button>
                                );
                            })}
                            <p className="text-[10px] text-slate-500 mt-2 px-1">
                                Enables all containerized tools. Exclusive mode.
                            </p>
                        </div>
                    )}

                    {/* Web Tools Tab */}
                    {activeTab === 'web' && (
                        <div className="space-y-1">
                            {isDockerGatewayActive && (
                                <p className="text-[10px] text-amber-500 mb-2 px-1">
                                    ⚠ Disable Docker mode first to select these tools.
                                </p>
                            )}
                            {webTools.map(tool => {
                                const isSelected = selectedMcpTools.includes(tool.label);
                                const isDisabledByDocker = isDockerGatewayActive;
                                return (
                                    <button
                                        key={tool.label}
                                        onClick={() => toggleMcpTool(tool.label)}
                                        disabled={!canSelectTools || isDisabledByDocker}
                                        title={isDisabledByDocker ? 'Disable Docker mode first to select this tool' : tool.label}
                                        className={`
                                            w-full text-left px-3 py-2 text-sm rounded-md
                                            transition-all duration-150
                                            flex items-center justify-between
                                            ${isSelected
                                                ? 'bg-sky-600/20 text-sky-400'
                                                : isDisabledByDocker
                                                    ? 'text-slate-500 cursor-not-allowed opacity-50'
                                                    : canSelectTools
                                                        ? 'text-slate-300 hover:bg-slate-800'
                                                        : 'text-slate-500 cursor-not-allowed'}
                                        `}
                                    >
                                        <span className="font-medium">{tool.label}</span>
                                        {isSelected && <CheckIcon className="w-4 h-4 text-sky-400" />}
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    {/* Local Tools Tab */}
                    {activeTab === 'local' && (
                        <div className="space-y-1">
                            {isDockerGatewayActive && (
                                <p className="text-[10px] text-amber-500 mb-2 px-1">
                                    ⚠ Disable Docker mode first to select these tools.
                                </p>
                            )}
                            {localTools.map(tool => {
                                const isSelected = selectedMcpStdio.includes(tool.command);
                                const isDisabledByDocker = isDockerGatewayActive;
                                return (
                                    <button
                                        key={tool.command}
                                        onClick={() => toggleMcpStdio(tool.command)}
                                        disabled={!canSelectTools || isDisabledByDocker}
                                        title={isDisabledByDocker ? 'Disable Docker mode first to select this tool' : tool.label}
                                        className={`
                                            w-full text-left px-3 py-2 text-sm rounded-md
                                            transition-all duration-150
                                            flex items-center justify-between
                                            ${isSelected
                                                ? 'bg-sky-600/20 text-sky-400'
                                                : isDisabledByDocker
                                                    ? 'text-slate-500 cursor-not-allowed opacity-50'
                                                    : canSelectTools
                                                        ? 'text-slate-300 hover:bg-slate-800'
                                                        : 'text-slate-500 cursor-not-allowed'}
                                        `}
                                    >
                                        <span className="font-medium">{tool.label}</span>
                                        {isSelected && <CheckIcon className="w-4 h-4 text-sky-400" />}
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Footer hint */}
                {!canSelectTools && (
                    <div className="px-3 py-2 bg-slate-800/50 border-t border-slate-700/50">
                        <p className="text-[10px] text-slate-500">
                            Switch to Tools mode to select tools.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
};
