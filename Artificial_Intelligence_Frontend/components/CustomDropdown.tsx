import React, { useState, useRef, useEffect } from 'react';

interface CustomDropdownProps {
    options: string[];
    value: string;
    onChange: (value: string) => void;
    label?: string;
    placeholder?: string;
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

export const CustomDropdown: React.FC<CustomDropdownProps> = ({
    options,
    value,
    onChange,
    label,
    placeholder = "Select an option"
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, []);

    const handleSelect = (option: string) => {
        onChange(option);
        setIsOpen(false);
    };

    return (
        <div className="relative w-full" ref={dropdownRef}>
            {label && (
                <label className="text-xs text-slate-500 mb-1 block font-medium uppercase tracking-wider">
                    {label}
                </label>
            )}

            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className={`
                    w-full flex items-center justify-between 
                    bg-slate-800/50 backdrop-blur-sm
                    border border-slate-600/50 
                    text-slate-200 text-xs 
                    rounded-lg px-3 py-2.5
                    hover:bg-slate-700/50 hover:border-sky-500/50
                    focus:outline-none focus:ring-2 focus:ring-sky-500/50
                    transition-all duration-200 ease-in-out
                    ${isOpen ? 'ring-2 ring-sky-500/50 border-sky-500' : ''}
                `}
            >
                <span className="truncate">
                    {value ? (value.charAt(0).toUpperCase() + value.slice(1)) : placeholder}
                </span>
                <ChevronDownIcon
                    className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                />
            </button>

            {/* Dropdown Menu */}
            <div
                className={`
                    absolute z-50 w-full mt-1.5
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
                <div className="max-h-60 overflow-y-auto py-1 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                    {options.map((option) => (
                        <button
                            key={option}
                            type="button"
                            onClick={() => handleSelect(option)}
                            className={`
                                w-full text-left px-3 py-2 text-xs
                                transition-colors duration-150
                                flex items-center
                                ${value === option
                                    ? 'bg-sky-600/20 text-sky-400 font-medium'
                                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'}
                            `}
                        >
                            {value === option && (
                                <div className="w-1.5 h-1.5 rounded-full bg-sky-400 mr-2 flex-shrink-0" />
                            )}
                            <span className={value === option ? '' : 'pl-3.5'}>
                                {option.charAt(0).toUpperCase() + option.slice(1)}
                            </span>
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
};
