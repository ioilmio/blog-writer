import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { FileEdit, Save, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { Article, ArticleInput } from './types/Article';
// import PipelineDashboard from './PipelineDashboard';
import CategoryMultiSelect, { CategoryOption } from './CategoryMultiSelect';

function App() {
  const [article, setArticle] = useState<Article | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isApproved, setIsApproved] = useState(false); // NEW
  const { register, handleSubmit, formState: { errors } } = useForm<ArticleInput>();
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);

  useEffect(() => {
    fetch('/landing_categories.json')
      .then(res => res.json())
      .then((data: Array<{ name: string; subs: Array<{ name: string }> }>) => {
        // Transform to CategoryOption[]
        const opts: CategoryOption[] = data.map((cat) => ({
          label: cat.name,
          value: cat.name,
          subs: (cat.subs || []).map((sub) => ({ label: sub.name, value: sub.name }))
        }));
        console.log(opts);
        
        setCategories(opts);
      });
  }, []);

  const onSubmit = async (data: ArticleInput) => {
    try {
      setIsGenerating(true);
      console.log('[App] Submitting article generation request', { data, selectedCategories });
      // If batching, send to batch endpoint
      if (selectedCategories.length > 1) {
        const batchPayload = selectedCategories.map(catVal => {
          const [, sub] = catVal.split('::');
          return { ...data, topic: sub };
        });
        console.log('[App] Sending batch generation request', batchPayload);
        await fetch('http://localhost:8000/api/pipeline/batch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ articles: batchPayload })
        });
        setArticle(null);
      } else {
        // Single
        console.log('[App] Sending single article generation request', { ...data, topic: selectedCategories[0] ? selectedCategories[0].split('::')[1] : data.topic });
        const response = await fetch('http://localhost:8000/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...data, topic: selectedCategories[0] ? selectedCategories[0].split('::')[1] : data.topic })
        });
        if (!response.ok) throw new Error('Failed to generate article');
        const result = await response.json();
        setArticle(result);
        setIsApproved(false); // Reset approval state for new article
        console.log('[App] Article generated:', result);
      }
    } catch (error) {
      console.error('[App] Error generating article:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  // Approve and save handler
  const handleApproveAndSave = async () => {
    if (!article) return;
    try {
      setIsSaving(true);
      const response = await fetch('http://localhost:8000/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(article),
      });
      if (!response.ok) throw new Error('Failed to save article');
      const result = await response.json();
      console.log('Article saved:', result.path);
      setIsApproved(true);
    } catch (error) {
      console.error('Error saving article:', error);
    } finally {
      setIsSaving(false);
    }
  };

  // Only allow image generation after approval
  const handleGenerateAndValidateImages = async () => {
    if (!article || !isApproved) return;
    try {
      setIsSaving(true);
      // Now trigger image step (pipeline)
      const imageRes = await fetch('http://localhost:8000/api/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...article, step: 'image' })
      });
      if (!imageRes.ok) throw new Error('Failed to trigger image step');
      const imageResult = await imageRes.json();
      console.log('Image step triggered:', imageResult);
    } catch (error) {
      console.error('Error generating/validating images:', error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Category multi-select UI */}
        <CategoryMultiSelect options={categories} value={selectedCategories} onChange={setSelectedCategories} />
        {/* Existing article generator UI */}
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
              <div className="flex flex-col gap-2">
                <div className="text-lg font-bold text-gray-800 mb-2">{article.title}</div>
                {!isApproved ? (
                  <button
                    onClick={handleApproveAndSave}
                    disabled={isSaving}
                    className="bg-green-500 text-white px-4 py-2 rounded-md hover:bg-green-600 disabled:opacity-50 flex items-center gap-2"
                  >
                    {isSaving ? (
                      <>
                        <Loader2 className="animate-spin" size={16} />
                        Saving & Approving...
                      </>
                    ) : (
                      <>
                        <Save size={16} />
                        Approve & Save Article
                      </>
                    )}
                  </button>
                ) : (
                  <button
                    onClick={handleGenerateAndValidateImages}
                    disabled={isSaving}
                    className="bg-blue-500 text-white px-4 py-2 rounded-md hover:bg-blue-600 disabled:opacity-50 flex items-center gap-2"
                  >
                    {isSaving ? (
                      <>
                        <Loader2 className="animate-spin" size={16} />
                        Generating & Validating Images...
                      </>
                    ) : (
                      <>
                        <Save size={16} />
                        Generate and Validate Images
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
            <div className="prose max-w-none">
              <ReactMarkdown>{article.content}</ReactMarkdown>
            </div>
          </div>
        )}
        {/* Pipeline Dashboard UI */}
        {/* <PipelineDashboard /> */}
      </div>
    </div>
  );
}

export default App;