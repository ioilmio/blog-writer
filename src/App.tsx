import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { FileEdit, Save, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { Article, ArticleInput } from './types/Article';

function App() {
  const [article, setArticle] = useState<Article | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const { register, handleSubmit, formState: { errors } } = useForm<ArticleInput>();

  const onSubmit = async (data: ArticleInput) => {
    try {
      setIsGenerating(true);
      const response = await fetch('http://localhost:8000/api/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
      
      if (!response.ok) throw new Error('Failed to generate article');
      
      const result = await response.json();
      setArticle(result);
    } catch (error) {
      console.error('Error generating article:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!article) return;
    
    try {
      setIsSaving(true);
      const response = await fetch('http://localhost:8000/api/save', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(article),
      });
      
      if (!response.ok) throw new Error('Failed to save article');
      
      const result = await response.json();
      console.log('Article saved:', result.path);
    } catch (error) {
      console.error('Error saving article:', error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-6">Blog Article Generator</h1>
          
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Topic
              </label>
              <input
                {...register('topic', { required: 'Topic is required' })}
                className="w-full p-2 border rounded-md"
                placeholder="Enter your topic..."
              />
              {errors.topic && (
                <p className="text-red-500 text-sm mt-1">{errors.topic.message}</p>
              )}
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Additional Context (optional)
              </label>
              <textarea
                {...register('additional_context')}
                className="w-full p-2 border rounded-md"
                rows={4}
                placeholder="Add any additional context..."
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Customer Audience
              </label>
              <input
                type="checkbox"
                {...register('customer_audience')}
                className="mr-2"
              />
              <span className="text-sm text-gray-600">If checked, the article will be focused on customers. If unchecked, it will be focused on professionals.</span>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Tipo di informazione
              </label>
              <select
                {...register('information_type')}
                className="w-full p-2 border rounded-md"
                defaultValue=""
              >
                <option value="">Seleziona il tipo di informazione...</option>
                <option value="guide pratiche">Guide pratiche</option>
                <option value="ultime tendenze">Ultime tendenze</option>
                <option value="normative">Normative</option>
                <option value="consigli per professionisti">Consigli per professionisti</option>
                <option value="consigli per clienti">Consigli per clienti</option>
              </select>
            </div>
            
            <button
              type="submit"
              disabled={isGenerating}
              className="bg-blue-500 text-white px-4 py-2 rounded-md hover:bg-blue-600 disabled:opacity-50 flex items-center gap-2"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="animate-spin" size={16} />
                  Generating...
                </>
              ) : (
                <>
                  <FileEdit size={16} />
                  Generate Article
                </>
              )}
            </button>
          </form>
        </div>

        {article && (
          <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Preview</h2>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="bg-green-500 text-white px-4 py-2 rounded-md hover:bg-green-600 disabled:opacity-50 flex items-center gap-2"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="animate-spin" size={16} />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save size={16} />
                    Save Article
                  </>
                )}
              </button>
            </div>
            
            <div className="prose max-w-none">
              <ReactMarkdown>{article.content}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;