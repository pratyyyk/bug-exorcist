import React from 'react';

// Define the shape of the props based on the issue requirements
interface BugCardProps {
  id: string | number;
  errorMessage: string;
  severity: 'High' | 'Low';
  status: 'Detected' | 'Fixing' | 'Fixed';
}

const BugCard: React.FC<BugCardProps> = ({ id, errorMessage, severity, status }) => {
  // Helper function to determine color styles based on status
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Detected':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'Fixing':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'Fixed':
        return 'bg-green-100 text-green-800 border-green-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  // Helper to visually distinguish severity
  const getSeverityColor = (severity: string) => {
    return severity === 'High' 
      ? 'text-red-600 font-bold' 
      : 'text-blue-600 font-medium';
  };

  return (
    <div className="border rounded-lg shadow-sm p-4 mb-4 bg-white hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs font-mono text-gray-500">ID: {id}</span>
        <span className={`px-2 py-1 rounded-full text-xs font-semibold border ${getStatusColor(status)}`}>
          {status}
        </span>
      </div>
      
      <div className="mb-3">
        <h3 className="text-lg font-semibold text-gray-900">Error Details</h3>
        <p className="text-gray-700 mt-1 break-words font-mono text-sm bg-gray-50 p-2 rounded">
          {errorMessage}
        </p>
      </div>

      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-600">Severity:</span>
        <span className={getSeverityColor(severity)}>
          {severity}
        </span>
      </div>
    </div>
  );
};

export default BugCard;