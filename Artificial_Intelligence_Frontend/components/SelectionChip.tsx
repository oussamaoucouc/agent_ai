import React from 'react';
import { CloseIcon } from './icons';

interface SelectionChipProps {
    label: string;
    onRemove?: () => void;
    variant?: 'default' | 'count';
    disabled?: boolean;
}

/**
 * A small pill-shaped chip component for showing selected items.
 * Used in VoiceSelector and ToolsSelector to display current selections.
 */
export const SelectionChip: React.FC<SelectionChipProps> = ({
    label,
    onRemove,
    variant = 'default',
    disabled = false,
}) => {
    if (variant === 'count') {
        return (
            <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-medium bg-sky-500/20 text-sky-300 rounded-full border border-sky-500/30">
                {label}
            </span>
        );
    }

    return (
        <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full border transition-all duration-150 ${disabled
                ? 'bg-slate-700/30 text-slate-500 border-slate-600/30'
                : 'bg-slate-700/50 text-slate-300 border-slate-600 hover:bg-slate-700'
                }`}
        >
            <span className="truncate max-w-[80px]" title={label}>
                {label}
            </span>
            {onRemove && !disabled && (
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        onRemove();
                    }}
                    className="shrink-0 p-0.5 rounded-full hover:bg-slate-600 text-slate-400 hover:text-slate-200 transition-colors"
                    aria-label={`Remove ${label}`}
                >
                    <CloseIcon className="w-2.5 h-2.5" />
                </button>
            )}
        </span>
    );
};
