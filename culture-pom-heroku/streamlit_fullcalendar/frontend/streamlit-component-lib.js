(function(window) {
  'use strict';
  
  window.Streamlit = {
    RENDER_EVENT: 'streamlit:render',
    events: {
      addEventListener: function(type, callback) {
        window.addEventListener(type, callback);
      }
    },
    setComponentReady: function() {
      window.parent.postMessage({type: 'streamlit:componentReady', apiVersion: 1}, '*');
    },
    setFrameHeight: function(height) {
      window.parent.postMessage({type: 'streamlit:setFrameHeight', height: height}, '*');
    },
    setComponentValue: function(value) {
      window.parent.postMessage({type: 'streamlit:setComponentValue', value: value}, '*');
    }
  };
  
  window.addEventListener('message', function(event) {
    if (event.data.type === 'streamlit:render') {
      var renderEvent = new CustomEvent('streamlit:render', {detail: {args: event.data.args}});
      window.dispatchEvent(renderEvent);
    }
  });
})(window);
