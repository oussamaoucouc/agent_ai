import React from 'react';

interface ModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel?: () => void;
  confirmText?: string;
  cancelText?: string;
  showCancel?: boolean;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  title,
  message,
  onConfirm,
  onCancel,
  confirmText = 'OK',
  cancelText = 'Cancel',
  showCancel = false,
}) => {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4 backdrop-blur-sm"
      aria-labelledby="modal-title"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-md p-6 space-y-4 bg-slate-800/60 backdrop-blur-xl border border-slate-500/30 rounded-xl shadow-2xl">
        <h2 id="modal-title" className="text-lg font-bold text-white">
          {title}
        </h2>
        <p className="text-slate-300 text-sm">
          {message}
        </p>
        <div className="flex justify-end gap-3 pt-2">
          {showCancel && onCancel && (
            <button
              onClick={onCancel}
              className="px-4 py-2 text-sm font-medium text-slate-300 bg-slate-700/50 border border-slate-600 hover:bg-white/10 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-500 focus:ring-offset-slate-900"
            >
              {cancelText}
            </button>
          )}
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm font-medium text-white bg-sky-600 hover:bg-sky-700 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-500 focus:ring-offset-slate-900"
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};